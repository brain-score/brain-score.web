CREATE MATERIALIZED VIEW mv_final_model_context AS
WITH
  -- SUGGESTION: This is a bit of a mess. Consider refactoring.
  -- These CTEs for the model_meta and submission_meta do not provide
  -- utility vs normal joins
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
  -- Ranking models based on "average_<domain>" benchmarks if they are public.
  -- SUGGESTION:This is currently not used in the Django index.py as private leaderboards
  -- necessitate re-ranking. If re-ranking is not needed, this would have
  -- sped up the leaderboard view by a couple hundred milliseconds. Consider still keeping
  -- this to quickly see top models per domain from within the database.
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

  -- Hacky CTEs for layers extraction, processing and storing into JSONB.
  -- Necessary because layer information is stored in a piece-wise manner in
  -- the brainscore_score.comment field. Could be cleaned up.
  -- SUGGESTION: This orders the layers in alphabetical order. In Django, we
  -- reorder the layers based on V1>V2>V4>IT. Consider adding it to this step
  -- and removing it from Django.
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
      "order" AS region_order  -- "order" is a reserved SQL keyword, so use quotes to specify it is a column name
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
  0 AS num_secondary_models,
  -- Model metadata for filters and cards: v2 record first, v1 brainscore_modelmeta as fallback
  jsonb_build_object(
    -- v2 family mapped to the v1 filter labels (core legacy_projection); other families fall back to v1
    'architecture', COALESCE(CASE md.architecture_family
        WHEN 'convolutional_neural_network' THEN 'DCNN'
        WHEN 'vision_transformer' THEN 'Transformer'
        WHEN 'recurrent_convolutional_neural_network' THEN 'Recurrent'
        WHEN 'hybrid_convolutional_transformer' THEN 'Hybrid'
        WHEN 'raw_pixels' THEN 'Pixels'
      END, mm2.architecture),
    'model_family', mm2.model_family,
    'total_parameter_count', COALESCE(md.parameter_count, mm2.total_parameter_count),
    'trainable_parameter_count', mm2.trainable_parameter_count,
    'total_layers', mm2.total_layers,
    'trainable_layers', mm2.trainable_layers,
    'model_size_mb', mm2.model_size_mb,
    'training_dataset', mm2.training_dataset,
    'task_specialization', mm2.task_specialization,
    'brainscore_link', mm2.brainscore_link,
    'hugging_face_link', mm2.hugging_face_link,
    'runnable', mm2.runnable,
    'extra_notes', mm2.extra_notes
  ) AS model_meta
FROM model_meta mm
LEFT JOIN brainscore_user u ON mm.owner_id = u.id
LEFT JOIN submission_meta sm ON mm.submission_id = sm.submission_id
LEFT JOIN brainscore_user u2 ON sm.submitter_id = u2.id
LEFT JOIN model_ranks mr ON mm.id = mr.model_id
LEFT JOIN mv_model_scores_json sc ON mm.id = sc.model_id
LEFT JOIN reference_meta rm ON mm.reference_id = rm.reference_id
LEFT JOIN final_layers fl ON mm.id = fl.model_id
LEFT JOIN brainscore_modelmeta mm2 ON mm.id = mm2.model_id
LEFT JOIN brainscore_model_metadata md
  ON lower(md.domain) = lower(mm.domain) AND lower(md.identifier) = lower(mm.name)
WHERE
  -- Remove models with no valid scores (to be consistent with legacy implementation)
  -- At least one score is valid (not '', not 'X', not NULL, not 'NaN')
  EXISTS (
    SELECT 1
    FROM jsonb_array_elements(sc.scores) AS score
    WHERE
      (score->>'score_ceiled') IS NOT NULL
      AND (score->>'score_ceiled') <> 'X'
  );
