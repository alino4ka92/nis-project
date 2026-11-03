SELECT count() AS matched_rows, sum(ResolutionWidth) AS width_sum
FROM {database:Identifier}.{table:Identifier}
WHERE UserID = 1313338681122956954;
