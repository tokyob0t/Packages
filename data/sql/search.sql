SELECT
    *
FROM
    packages
WHERE
    name LIKE ?
LIMIT
    ?;
