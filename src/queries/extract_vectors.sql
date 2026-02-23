WITH raw_groups AS (
  SELECT 
    castor,
    ARRAY_CONCAT(
      IF(category_code LIKE '%men%', ['men'], []),
      IF(category_code LIKE '%ladies%', ['ladies'], []),
      IF(category_code LIKE '%boy50-98%' OR category_code LIKE '%newborn50-98%', ['boy_50_98'], []),
      IF(category_code LIKE '%boy92-140%' OR category_code LIKE '%boy92-170%', ['boy_92_140'], []),
      IF(category_code LIKE '%boy92-170%' OR category_code LIKE '%boy134-170%', ['boy_134_170'], []),
      IF(category_code LIKE '%girl50-98%' OR category_code LIKE '%newborn50-98%', ['girl_50_98'], []),
      IF(category_code LIKE '%girl92-140%' OR category_code LIKE '%girl92-170%', ['girl_92_140'], []),
      IF(category_code LIKE '%girl92-170%' OR category_code LIKE '%girl134-170%', ['girl_134_170'], [])
    ) AS potential_groups
  FROM 
    `$articles_table`
  WHERE 
    country_code = 'GB' 
    AND buyable_status = 1
),

aggregated_groups AS (
  SELECT 
    castor,
    ARRAY_AGG(DISTINCT group_name) AS `groups`
  FROM 
    raw_groups, 
    UNNEST(potential_groups) AS group_name
  GROUP BY 
    castor
)

SELECT 
  a.castor, 
  a.features, 
  b.`groups`
FROM 
  `$features_table` AS a
JOIN 
  aggregated_groups AS b
  ON a.castor = b.castor