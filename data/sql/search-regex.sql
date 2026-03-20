SELECT
    *
FROM
    packages
WHERE
    name REGEXP ?
LIMIT
    ?;
