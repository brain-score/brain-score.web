-- THIS STILL IS A WORK IN PROGRESS AND NEEDS TO BE CLEANED UP. 
-- THERE ARE STILL MATERIALIZED VIEWS THAT ARE NOT USED ANYMORE.


-- ***************************************************************
--
--  _get_benchmarks()
--
-- ***************************************************************

-- ***************************************************************
-- STEP 1: Build the Recursive Benchmark Tree with a DFS Sort Path
-- For roots, use LPAD(order::text, 5, '0'); for children,
-- concatenate the parent's sort_path, a hyphen, and LPAD(child.order::text, 5, '0')
-- (and optionally the child identifier for tie-breaking).
-- ***************************************************************
DROP MATERIALIZED VIEW IF EXISTS mv_benchmark_tree CASCADE;
CREATE MATERIALIZED VIEW mv_benchmark_tree AS
WITH RECURSIVE tree AS (
  -- Anchor: roots (Capture all benchmarks regardless of visibility)
  SELECT
    bt.identifier,
    bt.parent_id,
    bt.domain,
    bt."order",
    bt.visible,
    bt.owner_id,
    bt.reference_id,
    0 AS depth,
    LPAD(bt."order"::text, 5, '0') || '-' || bt.identifier AS sort_path,
    bt.identifier AS root_parent
  FROM brainscore_benchmarktype bt
    WHERE bt.parent_id IS NULL

  UNION ALL

  -- Recursive part: join children using the text-based parent_id
  -- Propogate the parent's root_parent
  SELECT
    c.identifier,
    c.parent_id,
    c.domain,
    c."order",
    c.visible,
    c.owner_id,
    c.reference_id,
    p.depth + 1 AS depth,
    p.sort_path || '-' || LPAD(c."order"::text, 5, '0') || '-' || c.identifier AS sort_path,
    p.root_parent
  FROM brainscore_benchmarktype c
  JOIN tree p ON c.parent_id = p.identifier
)
SELECT * FROM tree;

-------------------------------------------------------------
-- STEP 2: Aggregate Immediate Children for Each Benchmark
-------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_benchmark_children CASCADE;
CREATE MATERIALIZED VIEW mv_benchmark_children AS
SELECT
  parent_id,
  jsonb_agg(identifier ORDER BY "order") AS children
FROM mv_benchmark_tree
WHERE parent_id IS NOT NULL
GROUP BY parent_id;

-------------------------------------------------------------
-- STEP 3: For Each Benchmark Type, Pick the Latest Instance (for leaves)
-------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_latest_benchmark_instance CASCADE;
CREATE MATERIALIZED VIEW mv_latest_benchmark_instance AS
SELECT
  bi.benchmark_type_id,
  MAX(bi.version) AS latest_version
FROM brainscore_benchmarkinstance bi
GROUP BY bi.benchmark_type_id;

-------------------------------------------------------------
-- STEP 4: Mark Each Benchmark as Leaf (has no children) or Parent
-- Here we determine if a given node in the tree is a leaf.
-------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_leaf_status CASCADE;
CREATE MATERIALIZED VIEW mv_leaf_status AS
SELECT
  t.identifier AS benchmark_identifier,
  -- A node is a leaf if no row in mv_benchmark_tree has its parent_id equal to this identifier.
  NOT EXISTS (
    SELECT 1
    FROM mv_benchmark_tree sub
    WHERE sub.parent_id = t.identifier
  ) AS is_leaf,
  t.depth,
  t.sort_path
FROM mv_benchmark_tree t;

-------------------------------------------------------------
-- STEP 5: Final Benchmark Context
-- Join the tree, leaf-status, latest instance data, and children.
-- For leaves we use the latest instance version; for abstract parent nodes, version = 0.
-- Also, overall_order is computed by ordering on our DFS sort_path.
-- The descendant count is computed as the number of leaf nodes in the subtree
-- (minus 1 for a leaf itself).
-------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_final_benchmark_context CASCADE;
CREATE MATERIALIZED VIEW mv_final_benchmark_context AS
SELECT
  -- Benchmark type: our text-based primary key from BenchmarkType
  t.identifier AS benchmark_type_id,
  -- For leaf nodes, use the latest instance version; for abstract/dummy nodes, version is 0.
  CASE
    WHEN ls.is_leaf THEN COALESCE(li.latest_version, 0)
    ELSE 0
  END AS version,
  -- For leaves, take the ceiling from the instance; if missing, default to 'X'
  COALESCE(bi.ceiling::text, 'X') AS ceiling,
  bi.ceiling_error,
  bi.meta_id,
  -- Aggregate the immediate children from our benchmark children view.
  bc.children,
  -- Build the parent JSON object using the parent identifier from BenchmarkType.
  (
    SELECT row_to_json(p)
    FROM (
      SELECT pbt.identifier,
             pbt.domain,
             pbt.reference_id,
             pbt."order",
             pbt.parent_id,
             pbt.visible,
             pbt.owner_id
      FROM brainscore_benchmarktype pbt
      WHERE pbt.identifier = t.parent_id
    ) p
  ) AS parent,
  -- Use the propagated root_parent value.
  t.visible,
  t.owner_id,
  t.root_parent,
  t.depth,
  -- Include the domain column from mv_benchmark_tree
  t.domain AS domain,
  -- Include the benchmark's own reference_id
  t.reference_id AS benchmark_reference_id,
  -- Include the benchmark's reference information
  br.author AS benchmark_author,
  br.year AS benchmark_year,
  br.url AS benchmark_url,
  (br.author || ' et al., ' || br.year) AS benchmark_reference_identifier,
  br.bibtex AS benchmark_bibtex,
  -- Count descendant leaves: count leaves in the subtree (using the DFS sort_path) minus one if current is a leaf.
  (
    SELECT COUNT(*)
    FROM mv_leaf_status ls2
    JOIN mv_benchmark_tree t2 ON ls2.benchmark_identifier = t2.identifier
    WHERE ls2.is_leaf
      AND ls2.sort_path LIKE t.sort_path || '%'
      AND t2.visible=True
  ) - (CASE WHEN ls.is_leaf THEN 1 ELSE 0 END) AS number_of_all_children,
  -- Overall order is computed using a row_number ordered by the DFS sort_path.
  ROW_NUMBER() OVER (ORDER BY t.sort_path) - 1 AS overall_order,
  -- Build a versioned benchmark identifier (concatenating the identifier and version)
  t.identifier || '_v' || CASE
                             WHEN ls.is_leaf THEN COALESCE(li.latest_version, 0)
                             ELSE 0
                           END AS identifier,
  -- Compute short_name by stripping off the lab prefix (everything before the first dot; assumes lab prefix does not contain capital letters)
  -- A simpler approach was used by postgresql was running into issue with incorrect regex escaping
  CASE
      WHEN position('.' in t.identifier) > 0
           AND substring(t.identifier FROM 1 FOR position('.' in t.identifier) - 1) ~ '[A-Z]'
      THEN
          t.identifier
      WHEN position('.' in t.identifier) > 0 THEN
          substring(t.identifier FROM position('.' in t.identifier) + 1)
      ELSE
          t.identifier
  END AS short_name,
  bi.id AS benchmark_id
FROM mv_benchmark_tree t
JOIN mv_leaf_status ls ON t.identifier = ls.benchmark_identifier
LEFT JOIN mv_latest_benchmark_instance li
  ON t.identifier = li.benchmark_type_id AND ls.is_leaf
LEFT JOIN brainscore_benchmarkinstance bi
  ON bi.benchmark_type_id = t.identifier
     AND bi.version = CASE
                        WHEN ls.is_leaf THEN COALESCE(li.latest_version, 0)
                        ELSE 0
                      END
LEFT JOIN mv_benchmark_children bc
  ON t.identifier = bc.parent_id
LEFT JOIN brainscore_reference br
  ON t.reference_id = br.id; -- Join to get benchmark reference information




-- ***************************************************************
--
--  _get_models()
--
-- ***************************************************************

------------------------------------------------------------
-- STEP A: Model Metadata MV (mv_model_data)
-- This view selects the public model rows
-- and joins in reference, submission, and user info.
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_model_data CASCADE;
CREATE MATERIALIZED VIEW mv_model_data AS
SELECT
    m.id AS model_id,
    m.name,
    m.domain,
    m.public,
    m.competition,
    m.reference_id,
    r.url AS reference_link,
    m.owner_id AS "user",
    s.status AS build_status,
    s.submitter_id AS submitter,
    m.submission_id,
    s.jenkins_id,
    s.timestamp
FROM brainscore_model m
LEFT JOIN brainscore_reference r ON m.reference_id = r.id
LEFT JOIN brainscore_submission s ON m.submission_id = s.id;


------------------------------------------------------------
-- STEP B: Base Scores for Leaf Benchmarks (mv_base_scores)
-- Modify to include all combinations of models and benchmarks,
-- including missing scores as NULLs.
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_base_scores CASCADE;
CREATE MATERIALIZED VIEW mv_base_scores AS
WITH s_ranked AS (
  SELECT
    s.*,
    ROW_NUMBER() OVER (
      PARTITION BY s.model_id, s.benchmark_id
      ORDER BY
        (s.score_raw IS NOT NULL) DESC,  -- prioritize non-null score_raw
        s.score_raw DESC NULLS LAST      -- highest score_raw if both non-null
    ) AS rn
  FROM brainscore_score s
)
SELECT
  s.id,
  m.model_id,
  fbc.benchmark_type_id,
  fbc.benchmark_id,
  fbc.version,
  fbc.overall_order,
  s.score_raw,
  s.score_ceiled,
  s.error,
  s.comment,
  CASE WHEN s.score_raw IS NOT NULL THEN TRUE ELSE FALSE END AS is_complete
FROM
  -- All models
  (SELECT DISTINCT model_id FROM mv_model_data) m
CROSS JOIN
  -- All leaf benchmarks with valid benchmark_id (instances)
  (
    SELECT
      benchmark_id,
      benchmark_type_id,
      version,
      overall_order
    FROM mv_final_benchmark_context
    WHERE benchmark_id IS NOT NULL
      AND benchmark_type_id IN (
        SELECT benchmark_identifier
        FROM mv_leaf_status
        WHERE is_leaf = TRUE
      )
  ) fbc
LEFT JOIN s_ranked s
  ON s.model_id = m.model_id
  AND s.benchmark_id = fbc.benchmark_id
  AND s.rn = 1;


-- Separate view where score_ceiled is fixed for engineering benchmarks
DROP MATERIALIZED VIEW IF EXISTS mv_base_scores_fixed_engineering CASCADE;
CREATE MATERIALIZED VIEW mv_base_scores_fixed_engineering AS
SELECT
  bs.id,
  bs.model_id,
  bs.benchmark_type_id,
  bs.benchmark_id,
  bs.version,
  bs.overall_order,
  bs.score_raw::float8,
  CASE
    WHEN bs.comment ILIKE '%error%' AND bs.score_ceiled IS NULL THEN 'NaN'::float8
    WHEN fbt.root_parent ILIKE '%engineering%' THEN bs.score_raw::float8
    ELSE bs.score_ceiled::float8
  END AS score_ceiled,
  bs.error,
  bs.comment,
  bs.is_complete
FROM mv_base_scores bs
JOIN mv_final_benchmark_context fbt
  ON bs.benchmark_type_id = fbt.benchmark_type_id;


------------------------------------------------------------
-- STEP C: Aggregate Scores
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_direct_children CASCADE;
CREATE MATERIALIZED VIEW mv_direct_children AS
SELECT
  parent_id AS parent_identifier,
  jsonb_array_elements_text(children) AS child_identifier
FROM mv_benchmark_children;

DROP MATERIALIZED VIEW IF EXISTS mv_all_models CASCADE;
CREATE MATERIALIZED VIEW mv_all_models AS
SELECT DISTINCT model_id
FROM mv_base_scores_fixed_engineering;

DROP TABLE IF EXISTS final_agg_scores CASCADE;
CREATE TABLE final_agg_scores (
  score_id          integer,
  benchmark         text,       -- benchmark identifier (e.g. 'Marques2020')
  benchmark_id      integer,
  model_id          integer,
  score_raw         numeric,    -- the computed aggregated score_raw
  score_ceiled      numeric,    -- the computed aggregated score_ceiled
  depth             integer,
  sort_path         text,
  root_parent       text,
  error             numeric,
  comment           text,
  is_leaf           boolean
);



DROP FUNCTION IF EXISTS populate_final_agg_scores();
CREATE OR REPLACE FUNCTION populate_final_agg_scores() RETURNS void AS $$
DECLARE
  d integer;
  max_depth integer;
BEGIN
  -- Clear the table first.
  TRUNCATE final_agg_scores;

  -- Get max_depth, handle NULL case
  SELECT COALESCE(MAX(depth), 0) INTO max_depth FROM mv_benchmark_tree;
  
  -- Only proceed if we have data
  IF max_depth > 0 THEN
    -- Insert leaf scores.
    INSERT INTO final_agg_scores (score_id, benchmark, benchmark_id, model_id, score_raw, score_ceiled, depth, sort_path, root_parent, error, comment, is_leaf)
    SELECT
      bs.id,
      t.identifier,
      bs.benchmark_id,
      bs.model_id,
      bs.score_raw,
      bs.score_ceiled,
      t.depth,
      t.sort_path,
      t.root_parent,
      bs.error,
      bs.comment,
      TRUE    -- is_leaf= true
    FROM mv_benchmark_tree t
    JOIN mv_leaf_status ls ON t.identifier = ls.benchmark_identifier
    JOIN mv_base_scores_fixed_engineering bs ON bs.benchmark_type_id = t.identifier
    WHERE ls.is_leaf = TRUE
    AND t.visible = TRUE;

    -- Loop from max_depth-1 down to 0.
    FOR d IN REVERSE max_depth-1 .. 0 LOOP
      INSERT INTO final_agg_scores (benchmark, model_id, score_raw, score_ceiled, depth, sort_path, is_leaf)
      SELECT
        p.identifier AS benchmark,
        s.model_id,

        -- Compute score_raw
        CASE
          WHEN SUM(CASE WHEN s.score_raw IS NOT NULL AND s.score_raw = s.score_raw THEN 1 ELSE 0 END) > 0 THEN
            -- At least one numeric score
            SUM(COALESCE(NULLIF(s.score_raw, 'NaN'::float8), 0)) / COUNT(*)::float8
          WHEN SUM(CASE WHEN s.score_raw <> s.score_raw THEN 1 ELSE 0 END) > 0 THEN
            -- All scores are NaN or NULL, at least one is NaN
            'NaN'::float8
          ELSE
            -- All scores are NULL
            NULL
        END AS score_raw,

        -- Compute score_ceiled
        CASE
          WHEN SUM(CASE WHEN s.score_ceiled IS NOT NULL AND s.score_ceiled = s.score_ceiled THEN 1 ELSE 0 END) > 0 THEN
            SUM(COALESCE(NULLIF(s.score_ceiled, 'NaN'::float8), 0)) / COUNT(*)::float8
          WHEN SUM(CASE WHEN s.score_ceiled <> s.score_ceiled THEN 1 ELSE 0 END) > 0 THEN
            'NaN'::float8
          ELSE
            NULL
        END AS score_ceiled,

        p.depth,
        p.sort_path,
        FALSE -- is_leaf = false
      FROM mv_benchmark_tree p
      JOIN mv_benchmark_children bc ON p.identifier = bc.parent_id
      -- For each parent, join to its direct children's scores.
      JOIN final_agg_scores s
        ON s.benchmark = ANY (
             SELECT jsonb_array_elements_text(bc.children)
           ) AND s.model_id = s.model_id  -- Keep same model_id
      WHERE p.depth = d
      GROUP BY p.identifier, s.model_id, p.depth, p.sort_path;
    END LOOP;

    -- Update root parent
    UPDATE final_agg_scores f
    SET root_parent = (
      SELECT t0.identifier
      FROM mv_benchmark_tree t0
      WHERE t0.depth = 0
        AND f.sort_path LIKE t0.sort_path || '%'
      LIMIT 1
    )
    WHERE f.root_parent IS NULL;
  END IF;
END;
$$ LANGUAGE plpgsql;

DROP FUNCTION IF EXISTS fix_parent_scores();
CREATE OR REPLACE FUNCTION fix_parent_scores() RETURNS void AS $$
BEGIN
  -- Drop any existing intermediate table.
  DROP TABLE IF EXISTS intermediate_parent_stats;

  -- Create an intermediate table of parent statistics.
  CREATE TABLE intermediate_parent_stats AS
  WITH parent_stats AS (
    SELECT
      p.benchmark AS parent_benchmark,
      p.model_id,
      TRIM(p.sort_path) AS parent_sort_path,
      COUNT(*) FILTER (WHERE c.score_ceiled IS NULL) AS count_null,
      COUNT(*) FILTER (WHERE c.score_ceiled IS NOT NULL
                          AND c.score_ceiled::text ILIKE 'nan') AS count_nan,
      COUNT(*) FILTER (WHERE c.score_ceiled IS NOT NULL
                          AND c.score_ceiled::text NOT ILIKE 'nan') AS count_numeric
    FROM final_agg_scores p
    JOIN final_agg_scores c
      ON c.model_id = p.model_id
      AND c.depth = p.depth + 1
      AND TRIM(c.sort_path) LIKE TRIM(p.sort_path) || '-%'
    WHERE p.is_leaf = false
    GROUP BY p.benchmark, p.model_id, TRIM(p.sort_path)
  )
  SELECT * FROM parent_stats;

  -- Use the intermediate stats to update parent's score_ceiled.
  UPDATE final_agg_scores p
  SET score_ceiled = CASE
      WHEN ips.count_numeric = 0 AND ips.count_nan = 0 THEN NULL
      WHEN p.score_ceiled = 0 THEN 'NaN'::numeric
      WHEN ips.count_numeric = 0 AND ips.count_nan > 0 THEN 'NaN'::numeric
      ELSE p.score_ceiled
    END
  FROM intermediate_parent_stats ips
  WHERE p.benchmark = ips.parent_benchmark
    AND p.model_id = ips.model_id
    AND TRIM(p.sort_path) = ips.parent_sort_path
    AND p.score_ceiled = 0.0
    AND p.is_leaf = false;
END;
$$ LANGUAGE plpgsql;

--SELECT populate_final_agg_scores();
--SELECT fix_parent_scores();

------------------------------------------------------------
-- STEP D: Add metadata to aggregated scores
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_model_scores CASCADE;
CREATE MATERIALIZED VIEW mv_model_scores AS
SELECT
  fbc.benchmark_id,
  fbc.identifier AS benchmark_id_version,  -- Include the full identifier with version
  fa.benchmark    AS benchmark_identifier,
  fa.model_id,
  fa.score_raw,
  fa.score_ceiled,
  fbc.version,
  fbc.overall_order,
  fbc.root_parent,
  fbc.parent,
  fbc.meta_id,
  fbc.ceiling,
  fbc.ceiling_error,
  fbc.children,
  fbc.number_of_all_children,
  fbc.short_name,
  fa.is_leaf,
  fa.error,
  fa.comment,
  m.visual_degrees,
  m.id           AS model_pk,
  m.name         AS model_name,
  m.reference_id AS model_reference,
  m.public       AS public,
  m.competition  AS competition,
  m.domain       AS model_domain,
  fbc.domain     AS benchmark_domain,
  m.submission_id,
  fbc.depth,
  s.status       AS build_status,
  s.submitter_id AS submitter,
  s.timestamp    AS submission_timestamp,
  fbc.benchmark_author,
  fbc.benchmark_year,
  fbc.benchmark_url,
  fbc.benchmark_reference_identifier,
  fbc.benchmark_bibtex,
  fbc.visible   AS benchmark_visible,
  fbc.owner_id  AS benchmark_owner,
  m.public      AS model_public,
  m.owner_id    AS model_owner
FROM final_agg_scores fa
JOIN mv_final_benchmark_context fbc
  ON fbc.benchmark_type_id = fa.benchmark
JOIN brainscore_model m
  ON m.id = fa.model_id
LEFT JOIN brainscore_submission s
  ON s.id = m.submission_id;



------------------------------------------------------------
-- STEP E: Compute min/max per benchmark (for coloring)
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_benchmark_minmax CASCADE;
CREATE MATERIALIZED VIEW mv_benchmark_minmax AS

WITH constants AS (
    SELECT 'engineering'::text AS engineering_root
),

benchmarks AS (
    SELECT DISTINCT
        ms.benchmark_id_version,
        CONCAT(ms.benchmark_identifier, '_v', ms.version, '_v', ms.version) AS bench_id,
        ms.benchmark_identifier,
        ms.version,
        ms.root_parent
    FROM
        mv_model_scores ms
),

valid_scores AS (
    SELECT
        ms.benchmark_id_version,
        CONCAT(ms.benchmark_identifier, '_v', ms.version, '_v', ms.version) AS bench_id,
        ms.benchmark_identifier,
        ms.version,
        ms.score_ceiled::float8 AS score_ceiled,
        ms.root_parent
    FROM
        mv_model_scores ms
    WHERE
        ms.public = TRUE
        AND ms.score_ceiled IS NOT NULL
        AND ms.score_ceiled::text <> 'NaN'
        AND ms.score_ceiled::float8 <> 0  -- Exclude zeros introduced during aggregation
),

minmax_scores AS (
    SELECT
        vs.benchmark_id_version,
        vs.bench_id,
        vs.benchmark_identifier,
        MIN(vs.score_ceiled) AS min_score_raw,
        MAX(vs.score_ceiled) AS max_score_raw,
        vs.root_parent
    FROM
        valid_scores vs
    GROUP BY
        vs.benchmark_id_version,
        vs.bench_id,
        vs.benchmark_identifier,
        vs.root_parent
)

SELECT
    b.benchmark_identifier,
    b.bench_id,
    b.benchmark_id_version,
    CASE
        WHEN mm.min_score_raw IS NULL THEN 0  -- No scores available
        WHEN mm.min_score_raw = mm.max_score_raw THEN 0  -- Zero range
        ELSE mm.min_score_raw
    END AS min_score,
    CASE
        WHEN mm.min_score_raw IS NULL THEN 1  -- No scores available
        WHEN mm.min_score_raw = mm.max_score_raw THEN 1  -- Zero range
        WHEN b.root_parent ILIKE '%' || constants.engineering_root || '%' THEN mm.max_score_raw * 2.5
        ELSE mm.max_score_raw
    END AS max_score
FROM
    benchmarks b
LEFT JOIN
    minmax_scores mm ON mm.bench_id = b.bench_id
CROSS JOIN
    constants;


CREATE OR REPLACE FUNCTION representative_color_sql_precomputed(
    value FLOAT,
    min_value FLOAT,
    max_value FLOAT,
    root_parent TEXT
) RETURNS TEXT AS $$
DECLARE
    normalized_value FLOAT;
    idx INTEGER;
    color_hex TEXT;
    redgreen_colors TEXT[];
    gray_colors TEXT[];
    -- Variables for extracting RGB values:
    fallback_R INTEGER;
    fallback_G INTEGER;
    fallback_B INTEGER;
    R FLOAT;
    G FLOAT;
    B FLOAT;
    alpha FLOAT;
    slope FLOAT;
    intercept FLOAT;
    fallback_color TEXT;
    rgba_color TEXT;
    color_None TEXT := '#e0e1e2';
    gamma FLOAT := 0.5;  -- Gamma value to stretch high-end differences.
BEGIN
    -- Return a neutral (light grey) color if value is NULL or NaN.
    IF value IS NULL OR value::text ILIKE 'nan' THEN
        RETURN 'background-color: ' || color_None || ';';
    END IF;

    -- Normalize the input value between 0 and 1.
    IF max_value - min_value = 0 THEN
        normalized_value := 0.5;
    ELSE
        normalized_value := (value - min_value) / (max_value - min_value);
    END IF;
    normalized_value := GREATEST(LEAST(normalized_value, 1), 0);

    -- Apply gamma correction to emphasize differences at the top-end.
    normalized_value := POWER(normalized_value, 1.0/gamma);

    -- Optionally scale down the normalized value.
    normalized_value := 0.8 * normalized_value;
    normalized_value := GREATEST(LEAST(normalized_value, 1), 0);

    idx := FLOOR(100 * normalized_value)::INTEGER;
    IF idx > 100 THEN
        idx := 100;
    END IF;

    -- Precomputed color arrays generated from your Python code.
    redgreen_colors := ARRAY[
        '#ff0000', '#ff0000', '#ff0000', '#ff0000', '#fe0600', '#fe0600', '#fd0d01', '#fd0d01', '#fc1301', '#fb1901', '#fb1901', '#fa1f02', '#f92502', '#f92502', '#f82b02', '#f73103', '#f73103', '#f63703', '#f53d03', '#f44204', '#f44204', '#f44804', '#f34d04', '#f25305', '#f15805', '#f15805', '#f05e05', '#ef6306', '#ee6806', '#ed6e06', '#ec7307', '#eb7807', '#ea7d07', '#e98208', '#e88708', '#e88708', '#e78c08', '#e69109', '#e69509', '#e59a09', '#e49f0a', '#e3a30a', '#e2a80a', '#e1ac0a', '#e0b10b', '#dfb50b', '#deb90b', '#ddbe0c', '#dcc20c', '#dcc60c', '#dbca0d', '#d9d20d', '#d8d60d', '#d4d70e', '#cfd60e', '#c9d50e', '#c4d40f', '#bed40f', '#b9d30f', '#b4d20f', '#aed110', '#a4cf10', '#9fce10', '#9acd11', '#95cc11', '#90cc11', '#8bcb11', '#86ca12', '#7dc812', '#78c712', '#74c613', '#6fc613', '#6ac513', '#66c413', '#5dc214', '#59c114', '#55c014', '#51c015', '#48be15', '#44bd15', '#40bc16', '#3cbb16', '#38bb16', '#31b917', '#2db817', '#29b717', '#26b617', '#1eb518', '#1bb418', '#18b319', '#18b21c', '#19b124', '#19b028', '#19af2b', '#19ad32', '#1aad36', '#1aac39', '#1aaa40', '#1aa943', '#1ba947', '#1ba84a'
    ];
    gray_colors := ARRAY[
        '#f2f2f2', '#f2f2f2', '#f2f2f2', '#f2f2f2', '#f0f0f0', '#f0f0f0', '#eeeeee', '#eeeeee', '#ededed', '#ebebeb', '#ebebeb', '#e9e9e9', '#e7e7e7', '#e7e7e7', '#e6e6e6', '#e4e4e4', '#e4e4e4', '#e2e2e2', '#e0e0e0', '#dedede', '#dedede', '#dddddd', '#dbdbdb', '#d9d9d9', '#d7d7d7', '#d7d7d7', '#d6d6d6', '#d4d4d4', '#d2d2d2', '#d0d0d0', '#cecece', '#cdcdcd', '#cbcbcb', '#c9c9c9', '#c7c7c7', '#c7c7c7', '#c5c5c5', '#c4c4c4', '#c2c2c2', '#c0c0c0', '#bebebe', '#bdbdbd', '#bbbbbb', '#b9b9b9', '#b7b7b7', '#b5b5b5', '#b4b4b4', '#b2b2b2', '#b0b0b0', '#aeaeae', '#adadad', '#a9a9a9', '#a7a7a7', '#a5a5a5', '#a4a4a4', '#a2a2a2', '#a0a0a0', '#9e9e9e', '#9d9d9d', '#9b9b9b', '#999999', '#959595', '#949494', '#929292', '#909090', '#8e8e8e', '#8d8d8d', '#8b8b8b', '#878787', '#858585', '#848484', '#828282', '#808080', '#7e7e7e', '#7b7b7b', '#797979', '#777777', '#757575', '#727272', '#707070', '#6e6e6e', '#6c6c6c', '#6b6b6b', '#676767', '#656565', '#646464', '#626262', '#5e5e5e', '#5c5c5c', '#5b5b5b', '#595959', '#555555', '#545454', '#525252', '#4e4e4e', '#4c4c4c', '#4b4b4b', '#474747', '#454545', '#444444', '#424242'
    ];

    IF root_parent ILIKE '%engineering%' THEN
        color_hex := gray_colors[idx+1];  -- PostgreSQL arrays are 1-indexed.
    ELSE
        color_hex := redgreen_colors[idx+1];
    END IF;

    R := ('x' || substring(color_hex from 2 for 2))::bit(8)::int;
    G := ('x' || substring(color_hex from 4 for 2))::bit(8)::int;
    B := ('x' || substring(color_hex from 6 for 2))::bit(8)::int;

    IF max_value - min_value = 0 THEN
        alpha := 1.0;
    ELSE
        slope := -0.9 / (min_value - max_value);
        intercept := 0.1 - slope * min_value;
        alpha := slope * value + intercept;
    END IF;
    alpha := GREATEST(LEAST(alpha, 1), 0);

    fallback_R := ROUND(R);
    fallback_G := ROUND(G);
    fallback_B := ROUND(B);

    fallback_color := 'rgb(' || fallback_R || ', ' || fallback_G || ', ' || fallback_B || ')';
    rgba_color := 'rgba(' || R || ', ' || G || ', ' || B || ', ' || alpha || ')';

    RETURN 'background-color: ' || fallback_color || '; background-color: ' || rgba_color || ';';
END;
$$ LANGUAGE plpgsql IMMUTABLE;






------------------------------------------------------------
-- STEP F: Add min/max to mv_model_scores
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_model_scores_enriched CASCADE;
CREATE MATERIALIZED VIEW mv_model_scores_enriched AS
WITH base AS (
  SELECT --DISTINCT ON (ms.benchmark_identifier, ms.model_id)
    ms.*,
    bsfe.score_raw AS bs_score_raw,
    bsfe.score_ceiled AS bs_score_ceiled,
    -- Our chosen score:
    CASE
      WHEN ms.is_leaf AND ms.root_parent ILIKE '%engineering%' THEN bsfe.score_raw
      WHEN ms.is_leaf THEN bsfe.score_ceiled
      ELSE ms.score_ceiled
    END AS computed_score
  FROM mv_model_scores ms
  LEFT JOIN mv_base_scores_fixed_engineering bsfe
    ON bsfe.model_id = ms.model_id
   AND bsfe.benchmark_id = ms.benchmark_id
),
-- Compute median and best score per benchmark group using only valid numbers.
score_stats AS (
  SELECT DISTINCT ON (sub.bi)
    sub.bi,
    sub.ver,
    CASE WHEN COUNT(sub.valid_score) = 0 THEN 'NaN'::numeric
         ELSE percentile_cont(0.5) WITHIN GROUP (ORDER BY sub.valid_score)
    END AS median_score,
    COALESCE(MAX(sub.valid_score), 'NaN'::numeric) AS best_score
  FROM (
    SELECT
      b.benchmark_identifier AS bi,
      b.version AS ver,
      b.computed_score,
      CASE
        WHEN b.computed_score::text NOT ILIKE 'nan' THEN b.computed_score
        ELSE NULL
      END AS valid_score
    FROM base b
  ) sub
  GROUP BY sub.bi, sub.ver
),
-- Compute the per-benchmark ranking using row_number(), treating NaN as NULL so they rank last.
ranked AS (
  SELECT
    b.benchmark_identifier AS bi,
    b.version AS ver,
    b.model_id,
    row_number() OVER (
      PARTITION BY b.benchmark_identifier, b.version
      ORDER BY
        CASE
          WHEN b.computed_score::text ILIKE 'nan' THEN NULL
          ELSE b.computed_score
        END DESC NULLS LAST
    ) AS benchmark_rank
  FROM base b
)
SELECT --DISTINCT ON (b.benchmark_identifier, b.model_id)
  b.benchmark_id,
  b.benchmark_id_version,
  b.benchmark_identifier,
  b.model_id,
  b.score_raw,
  b.score_ceiled,
  b.version,
  b.overall_order,
  b.root_parent,
  b.parent,
  b.meta_id,
  b.ceiling,
  b.ceiling_error,
  b.children,
  b.number_of_all_children,
  b.short_name,
  b.is_leaf,
  b.error,
  b.comment,
  b.visual_degrees,
  b.model_pk,
  b.model_name,
  b.model_reference,
  b.public,
  b.competition,
  b.model_domain,
  b.benchmark_domain,
  b.submission_id,
  b.depth,
  b.build_status,
  b.submitter,
  b.submission_timestamp,
  b.benchmark_author,
  b.benchmark_year,
  b.benchmark_url,
  b.benchmark_reference_identifier,
  b.benchmark_bibtex,
  mmx.bench_id,
  b.benchmark_visible,
  b.benchmark_owner,
  b.model_public,
  b.model_owner,
  COALESCE(mmx.min_score, 0) AS min_score,
  COALESCE(mmx.max_score, 1) AS max_score,
  representative_color_sql_precomputed(
    b.computed_score::float,
    COALESCE(mmx.min_score, 0)::float,
    COALESCE(mmx.max_score, 1)::float,
    b.root_parent
  ) AS color,
  s.median_score,
  s.best_score,
  r.benchmark_rank
FROM base b
LEFT JOIN mv_benchmark_minmax mmx
  ON mmx.benchmark_identifier = b.benchmark_identifier
  AND mmx.benchmark_id_version = b.benchmark_identifier || '_v' || b.version
LEFT JOIN score_stats s
  ON s.bi = b.benchmark_identifier
 AND s.ver = b.version
LEFT JOIN ranked r
  ON r.bi = b.benchmark_identifier
 AND r.ver = b.version
 AND r.model_id = b.model_id;




------------------------------------------------------------
-- STEP G: Assemble json in _get_models() return
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_model_scores_json CASCADE;
CREATE MATERIALIZED VIEW mv_model_scores_json AS
WITH score_with_value AS (
    SELECT
        ms.*,
        b.score_raw AS base_score_raw,
        b.score_ceiled AS base_score_ceiled,
        CASE
            WHEN ms.is_leaf AND ms.root_parent ILIKE '%engineering%' THEN b.score_raw
            WHEN ms.is_leaf THEN b.score_ceiled
            ELSE ms.score_ceiled
        END AS score_ceiled_value,
        CASE
            WHEN ms.is_leaf THEN b.score_raw
            ELSE ms.score_raw
        END AS score_raw_value,
        to_jsonb(bm) AS meta
    FROM mv_model_scores_enriched ms
    LEFT JOIN mv_base_scores_fixed_engineering b
           ON b.benchmark_id = ms.benchmark_id
          AND b.model_id     = ms.model_id
    LEFT JOIN brainscore_benchmarkmeta bm
           ON bm.id = ms.meta_id
    WHERE ms.benchmark_domain = ms.model_domain
),
score_json AS (
    SELECT
        model_id,
        jsonb_agg(
            jsonb_build_object(
                'benchmark', jsonb_build_object(
                    'id',                benchmark_id,
                    'benchmark_type_id', benchmark_identifier,
                    'version',           version,
                    'ceiling',           ceiling,
                    'ceiling_error',     ceiling_error,
                    'meta_id',           meta_id,
                    'children',          children,
                    'parent',            parent,
                    'root_parent',       root_parent,
                    'depth',             depth,
                    'number_of_all_children', number_of_all_children,
                    'overall_order',     overall_order,
                    'identifier',        benchmark_identifier || '_v' || version,
                    'short_name',        short_name,
                    'author',            benchmark_author,
                    'year',              benchmark_year,
                    'url',               benchmark_url,
                    'reference_identifier', benchmark_reference_identifier,
                    'bibtex',            benchmark_bibtex,
                    'meta',              meta
                ),
                'versioned_benchmark_identifier', benchmark_identifier || '_v' || version,
                'score_raw', score_raw_value,
                'score_ceiled_raw', score_ceiled_value,
                'score_ceiled',
                  CASE
                    WHEN score_ceiled_value IS NULL THEN ''
                    WHEN score_ceiled_value::text ILIKE 'nan' THEN 'X'
                    WHEN score_ceiled_value < 1 THEN TRIM(LEADING '0' FROM TO_CHAR(score_ceiled_value, 'FM0.000'))
                    ELSE TO_CHAR(score_ceiled_value, 'FM0.000')
                  END,
                'error', error,
                'comment', comment,
                'visual_degrees', visual_degrees,
                'color', color,
                'median', median_score,
                'best', best_score,
                'rank', benchmark_rank,
                'is_complete', CASE WHEN score_ceiled_value IS NULL THEN 0 ELSE 1 END
            )
            ORDER BY overall_order
        ) AS scores
    FROM score_with_value
    GROUP BY model_id
)
SELECT
    model_id,
    scores
FROM score_json;





------------------------------------------------------------
-- STEP H: Join per-model score JSON with model metadata
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_final_model_context CASCADE;
CREATE MATERIALIZED VIEW mv_final_model_context AS
WITH
  -- Existing CTEs remain unchanged
  model_meta AS (
    SELECT
      m.id,
      m.name,
      m.reference_id,
      m.public,
      m.competition,
      m.domain,
      m.owner_id,
      m.submission_id,
      m.visual_degrees
    FROM brainscore_model m
  ),
  submission_meta AS (
    SELECT
      s.id AS submission_id,
      s.status AS build_status,
      s.submitter_id,
      s.timestamp,
      s.jenkins_id
    FROM brainscore_submission s
  ),
  model_ranks AS (
      SELECT
        ms.model_id,
        ms.model_domain,
        ms.comment,
        RANK() OVER (
          PARTITION BY ms.model_domain
          ORDER BY
            CASE
              WHEN ms.score_ceiled IS NOT NULL AND ms.score_ceiled::text NOT ILIKE 'nan' THEN 0
              WHEN ms.score_ceiled IS NOT NULL AND ms.score_ceiled::text ILIKE 'nan' THEN 1
              WHEN ms.score_ceiled IS NULL THEN 2
            END ASC,
            ms.score_ceiled DESC
        ) AS rank
      FROM mv_model_scores_enriched ms
      WHERE ms.benchmark_identifier = 'average_' || ms.model_domain
        AND ms.public = TRUE  -- Only rank public models
    ),
  reference_meta AS (
    SELECT
      r.id AS reference_id,
      r.author,
      r.year,
      r.url,
      r.bibtex
    FROM brainscore_reference r
  ),

  -- New CTEs for layers extraction and processing
  layer_comments AS (
    SELECT
      ms.model_id,
      ms.overall_order,
      -- Extract and clean the layers data from the comment
      REPLACE(SUBSTRING(ms.comment FROM LENGTH('layers: ') + 1), '''', '"') AS layers_json_str
    FROM
      mv_model_scores_enriched ms
    WHERE
      ms.comment IS NOT NULL AND ms.comment LIKE 'layers: %'
  ),
  layer_comments_parsed AS (
    SELECT
      model_id,
      overall_order,
      layers_json_str,
      -- Parse the layers_json_str into JSONB
      CASE
        WHEN layers_json_str IS NOT NULL THEN layers_json_str::jsonb
        ELSE NULL
      END AS layers_jsonb
    FROM
      layer_comments
    WHERE
      layers_json_str IS NOT NULL
  ),
  layer_keys AS (
    SELECT
      lc.model_id,
      lc.overall_order,
      kv.key AS region,
      kv.value AS layer
    FROM
      layer_comments_parsed lc,
      jsonb_each_text(lc.layers_jsonb) AS kv(key, value)
  ),
  layer_keys_ordered AS (
    SELECT
      lk.model_id,
      lk.region,
      lk.layer,
      ROW_NUMBER() OVER (PARTITION BY lk.model_id, lk.region ORDER BY lk.overall_order DESC) AS rn
    FROM
      layer_keys lk
  ),
  merged_layers AS (
    SELECT
      model_id,
      region,
      layer
    FROM
      layer_keys_ordered
    WHERE
      rn = 1
  ),
  region_order AS (
    SELECT
      identifier AS region,
      "order" AS region_order  -- "order" is a reserved keyword, so use quotes
    FROM brainscore_benchmarktype
  ),
  ordered_layers AS (
    SELECT
      ml.model_id,
      ml.region,
      ml.layer,
      COALESCE(ro.region_order, 0) AS region_order
    FROM
      merged_layers ml
    LEFT JOIN
      region_order ro ON ml.region = ro.region
  ),
  final_layers AS (
    SELECT
      model_id,
      jsonb_object_agg(region, layer ORDER BY region_order) AS layers
    FROM
      ordered_layers
    GROUP BY
      model_id
  )

SELECT
  mm.id AS model_id,
  mm.name,
  rm.author,
  rm.year,
  rm.url,
  (rm.author || ' et al., ' || rm.year) AS reference_identifier,
  rm.bibtex,
  to_jsonb(u.*) AS "user",
  to_jsonb(u.*) AS "owner",
  mm.public,
  mm.competition,
  mm.domain,
  mm.visual_degrees,
  fl.layers,  -- Include layers from 'final_layers'
  mr.rank,
  sc.scores,
  sm.build_status,
  to_jsonb(u2.*) AS "submitter",
  mm.submission_id,
  sm.jenkins_id,
  sm.timestamp,
  u2.id AS user_id,
  NULL::INTEGER AS primary_model_id,
  0 AS num_secondary_models
--   -- Additional columns from brainscore_modelmeta
--   mm2.architecture,
--   mm2.model_family,
--   mm2.total_parameter_count,
--   mm2.total_layers,
--   mm2.training_dataset,
--   mm2.task_specialization,
--   mm2.brainscore_link,
--   mm2.huggingface_link,
--   mm2.trainable_parameter_count,
--   mm2.trainable_layers,
--   mm2."model_size_MB", --wrap in quotes due to case errors
--   mm2.extra_notes
FROM model_meta mm
LEFT JOIN brainscore_user u ON mm.owner_id = u.id
LEFT JOIN submission_meta sm ON mm.submission_id = sm.submission_id
LEFT JOIN brainscore_user u2 ON sm.submitter_id = u2.id
LEFT JOIN model_ranks mr ON mm.id = mr.model_id
LEFT JOIN mv_model_scores_json sc ON mm.id = sc.model_id
LEFT JOIN reference_meta rm ON mm.reference_id = rm.reference_id
LEFT JOIN final_layers fl ON mm.id = fl.model_id;
-- LEFT JOIN brainscore_modelmeta mm2 ON mm.name = mm2.identifier;



--------------------------------------------------------------------------
--------------------------------------------------------------------------
--------------------------------------------------------------------------
--------------------------------------------------------------------------
------------REFRESH MATERIALIZED VIEWS AND POPULATE TABLE-----------------
--------------------------------------------------------------------------
--------------------------------------------------------------------------
--------------------------------------------------------------------------
--------------------------------------------------------------------------


CREATE OR REPLACE FUNCTION refresh_all_materialized_views() RETURNS void AS $$
BEGIN
  -- Refresh materialized views in the correct order
    RAISE NOTICE 'Refreshing Benchmark-related Context';
    REFRESH MATERIALIZED VIEW mv_benchmark_tree;
    REFRESH MATERIALIZED VIEW mv_benchmark_children;
    REFRESH MATERIALIZED VIEW mv_latest_benchmark_instance;
    REFRESH MATERIALIZED VIEW mv_leaf_status;
    REFRESH MATERIALIZED VIEW mv_final_benchmark_context;

    RAISE NOTICE 'Refreshing Model-related Tables';
    REFRESH MATERIALIZED VIEW mv_model_data;
    REFRESH MATERIALIZED VIEW mv_base_scores;
    REFRESH MATERIALIZED VIEW mv_base_scores_fixed_engineering;
    REFRESH MATERIALIZED VIEW mv_direct_children;
    REFRESH MATERIALIZED VIEW mv_all_models;

    -- Only try to populate if we have data
    IF EXISTS (SELECT 1 FROM mv_benchmark_tree LIMIT 1) THEN
        RAISE NOTICE 'Performing aggregation';
        PERFORM populate_final_agg_scores();
    END IF;

    -- Refresh additional materialized views depending on updated data
    RAISE NOTICE 'Refreshing Model-related Context';
    REFRESH MATERIALIZED VIEW mv_model_scores;
    REFRESH MATERIALIZED VIEW mv_benchmark_minmax;
    REFRESH MATERIALIZED VIEW mv_model_scores_enriched;
    REFRESH MATERIALIZED VIEW mv_model_scores_json;
    REFRESH MATERIALIZED VIEW mv_final_model_context;

    RAISE NOTICE 'Completed';
END;
$$ LANGUAGE plpgsql;


SELECT refresh_all_materialized_views();