SELECT count() AS matched_rows, sum(ResolutionWidth) AS width_sum
FROM {database:Identifier}.{table:Identifier}
WHERE CounterID = 62 AND EventDate >= '2013-07-14' AND EventDate < '2013-07-16';
