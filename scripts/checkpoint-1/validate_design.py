"""Check the experiment design against the frozen ClickBench answers and schema."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re


def validate(root, require_sqlglot=False):
    plan = json.loads((root / 'experiments/data-skipping.json').read_text())
    manifest = json.loads((root / plan['sample_manifest']).read_text())
    reference = json.loads((root / 'artifacts/checkpoint-1/clickbench-reference.json').read_text())
    with (root / 'artifacts/checkpoint-1/benchmark/run.tsv').open() as stream:
        answers = {int(row['query']): json.loads(row['answer'])
                   for row in csv.DictReader(stream, delimiter='\t') if row['status'] == 'OK'}
    if len(answers) != 43:
        raise ValueError('The source benchmark is incomplete')
    total = answers[1][0][0]
    if total != manifest['rows'] or total != plan['input_rows'] or total != reference['rows']:
        raise ValueError('Input sizes differ')
    if manifest['sample_sha256'] != plan['sample_sha256']:
        raise ValueError('Sample hashes differ')
    users = answers[16]
    if len(users) != 10 or len({user for user, _ in users}) != 10:
        raise ValueError('Q16 must contain ten distinct users')
    expected = {
        'Q01': reference['expected']['matched_rows'],
        'Q04': users[0][1], 'Q05': sum(count for _, count in users),
        'Q06': answers[2][0][0], 'Q07': answers[21][0][0], 'Q08': total,
    }
    identifiers = [query['id'] for query in plan['queries']]
    if identifiers != [f'Q{i:02}' for i in range(1, 9)]:
        raise ValueError('Query identifiers must be Q01-Q08 in order')
    for query in plan['queries']:
        if query.get('expected_matched_rows') != expected.get(query['id']):
            raise ValueError(f"Wrong expected count: {query['id']}")
        sql = (root / query['sql']).read_text()
        if '{database:Identifier}.{table:Identifier}' not in sql:
            raise ValueError(f"Missing table parameters: {query['id']}")
    q01 = (root / plan['queries'][0]['sql']).read_text()
    if not re.search(rf'CounterID\s*=\s*{reference["counter_id"]}\b', q01):
        raise ValueError('Q01 differs from the reference parameter')
    q04 = (root / plan['queries'][3]['sql']).read_text()
    if not re.search(rf'UserID\s*=\s*{users[0][0]}\b', q04):
        raise ValueError('Q04 user is absent from Q16')
    q05 = (root / plan['queries'][4]['sql']).read_text()
    user_list = re.search(r'UserID\s+IN\s*\(([^)]+)\)', q05, re.I)
    if not user_list or [int(x.strip()) for x in user_list[1].split(',')] != [u for u, _ in users]:
        raise ValueError('Q05 users differ from Q16')
    if '2013-07-15' not in answers[43][0][0] or answers[7][0] != ['2013-07-02', '2013-07-31']:
        raise ValueError('Date interval must be reviewed against the benchmark')
    if plan['query_order'] != {'base': identifiers, 'rotate_left_per_round': 1}:
        raise ValueError('Query order differs from the protocol')
    if plan['warmups'] < 1 or plan['measured_repeats'] < 3:
        raise ValueError('Insufficient warmups or repetitions')
    if len(plan['main_order_by_round']) != plan['measured_repeats']:
        raise ValueError('Main round count differs from the repetitions')
    for order in plan['main_order_by_round']:
        if sorted(order) != ['A', 'B']:
            raise ValueError('Main rounds must include A and B once')
    if len(plan['control_order_by_round']) != plan['measured_repeats']:
        raise ValueError('Control round count differs from the repetitions')
    for order in plan['control_order_by_round']:
        if sorted(order) != ['A', 'B', 'C', 'D']:
            raise ValueError('Control rounds must include A-D once')
    ddl = '\n'.join((root / f'sql/data-skipping/create-{suffix}.sql').read_text()
                    for suffix in ('main', 'controls'))
    for variant in plan['variants']:
        table = variant['table']
        match = re.search(rf'CREATE TABLE nis_skipping\.{table}\s+(.*?);', ddl, re.S)
        if not match or f"index_granularity = {variant['index_granularity']}" not in match[1]:
            raise ValueError(f'Wrong DDL granularity: {table}')
        for clause in ('PRIMARY KEY', 'ORDER BY'):
            if f"{clause} {variant['key']}" not in match[1]:
                raise ValueError(f'Wrong DDL key: {table}')
        for setting, value in plan['table_settings'].items():
            text = "''" if value == '' else str(value)
            if f'{setting} = {text}' not in match[1]:
                raise ValueError(f'Wrong table setting: {table}/{setting}')
    settings_sql = (root / 'sql/data-skipping/settings.sql').read_text()
    for name, value in plan['query_settings'].items():
        if f'SET {name} = {value};' not in settings_sql:
            raise ValueError(f'Query setting differs: {name}')

    parser_report = {'status': 'not_run'}
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        if require_sqlglot:
            raise RuntimeError('Install sqlglot==30.27.0 in an isolated environment') from None
    else:
        for query in plan['queries']:
            statement = sqlglot.parse_one((root / query['sql']).read_text(), read='clickhouse')
            if not isinstance(statement, exp.Select) or len(statement.expressions) != 2:
                raise ValueError(f"Wrong query shape: {query['id']}")
            columns = statement.expressions
            if (columns[0].alias != 'matched_rows' or columns[1].alias != 'width_sum'
                    or not isinstance(columns[0].this, exp.Count)
                    or not isinstance(columns[1].this, exp.Sum)
                    or columns[1].this.this.name != 'ResolutionWidth'):
                raise ValueError(f"Wrong query aggregates: {query['id']}")
            if any(statement.args.get(name) for name in ('group', 'order', 'limit', 'having')):
                raise ValueError(f"Unexpected result restriction: {query['id']}")
        count = 0
        opaque = []
        for path in sorted((root / 'sql/data-skipping').rglob('*.sql')):
            for statement in sqlglot.parse(path.read_text(), read='clickhouse',
                                          error_level=sqlglot.ErrorLevel.RAISE):
                if statement is None:
                    continue
                if isinstance(statement, exp.Command):
                    text = statement.sql(dialect='clickhouse')
                    if not re.fullmatch(r'OPTIMIZE TABLE nis_skipping\.\w+ FINAL', text):
                        raise ValueError(f'Unparsed SQL in {path}: {text}')
                    opaque.append(text)
                else:
                    count += 1
        parser_report = {'status': 'complete', 'version': sqlglot.__version__,
                         'parsed_statements': count, 'opaque_optimize_commands': opaque}
    paths = ['experiments/data-skipping.json', *[str(p.relative_to(root))
             for p in sorted((root / 'sql/data-skipping').rglob('*.sql'))]]
    return {
        'passed': True, 'source_commit': plan['source_commit'],
        'input_rows': total, 'query_count': len(identifiers),
        'variants': len(plan['variants']), 'expected_matched_rows': expected,
        'sql_parser': parser_report, 'clickhouse_execution': 'not_run',
        'scope': 'plan consistency and saved-answer evidence; no new performance measurements',
        'sha256': {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-sqlglot', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = validate(root, args.require_sqlglot)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            stream.write(text)
    print(text, end='')


if __name__ == '__main__':
    main()
