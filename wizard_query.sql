#wizard_query.sql

WITH wizard_input AS (
  SELECT
    @surface AS surface,
    @glass_type AS glass_type,
    @install_side AS install_side,
    @window_type AS window_type,
    @window_width_cm AS window_width_cm,

    @heat_priority AS heat_priority,
    @privacy_priority AS privacy_priority,
    @light_priority AS light_priority,

    @allow_diy AS allow_diy,
    @reflectivity_preference AS reflectivity_preference,
    @privacy_required AS privacy_required,
    @safety_required AS safety_required
),

filtered_products AS (
  SELECT
    p.*,

    ps.tsers,
    ps.visible_light_transmission,
    ps.visible_light_reflection_ext,
    ps.visible_light_reflection_int,

    r.heat_comfort_score,
    r.privacy_score,
    r.natural_light_score,

    w.*

  FROM `folias-juci.assistant.product_ranking` r

  JOIN `folias-juci.assistant.products` p
    ON r.product_id = p.product_id

  LEFT JOIN `folias-juci.assistant.product_specs` ps
    ON p.film_type = ps.product_id

  JOIN `folias-juci.assistant.product_glass_compatibility` g
    ON p.product_id = g.product_id

  CROSS JOIN wizard_input w

  WHERE
    p.surface = w.surface

    AND (
      w.safety_required = FALSE
      OR 'security' IN UNNEST(p.film_features)
    )

    AND (
      w.glass_type = 'unknown'
      OR g.glass_type = w.glass_type
    )

    AND (
      w.install_side = 'both'
      OR p.install_side = w.install_side
      OR p.install_side = 'both'
    )

    AND p.roll_width_cm >= w.window_width_cm

    AND (
      w.allow_diy = TRUE
      OR p.family != 'DIY'
    )

    AND (
      w.window_type != 'roof'
      OR p.roof_window_safe = TRUE
    )
),


scored_products AS (
  SELECT
    *,
   CASE
    WHEN
      (
        reflectivity_preference = 'any'
        OR (
          reflectivity_preference = 'mirror'
          AND visible_light_reflection_ext >= 15
        )
        OR (
          reflectivity_preference = 'neutral'
          AND visible_light_reflection_ext < 15
        )
      )

      AND (
        privacy_required = FALSE
        OR privacy_score >= 20
      )

      AND (
        heat_comfort_score >= 55
      )

      AND (
        safety_required = FALSE
        OR 'security' IN UNNEST(film_features)
      )

    THEN TRUE
    ELSE FALSE
    END AS exact_match,

    (
      COALESCE(heat_comfort_score,0) * heat_priority +
      COALESCE(privacy_score,0) * privacy_priority +
      COALESCE(natural_light_score,0) * light_priority
    ) / (heat_priority + privacy_priority + light_priority) AS final_score
  FROM filtered_products
)

SELECT
  product_id,
  sku,
  name,
  brand,
  family,
  image_url,
  product_url,

  -- ⭐ fizikai értékek
  tsers AS tser,
  visible_light_transmission,
  visible_light_reflection_ext,
  visible_light_reflection_int,


  exact_match,

  CASE
    WHEN exact_match THEN 'perfect'
    ELSE 'recommended'
  END AS match_type,


  -- ⭐ Hővédelem csillagok
  CASE
    WHEN heat_comfort_score >= 75 THEN '⭐⭐⭐⭐⭐ Kiváló'
    WHEN heat_comfort_score >= 65 THEN '⭐⭐⭐⭐ Nagyon jó'
    WHEN heat_comfort_score >= 55 THEN '⭐⭐⭐ Jó'
    WHEN heat_comfort_score >= 45 THEN '⭐⭐ Közepes'
    ELSE '⭐ Alap'
  END AS heat_rating,

  -- 👁 Belátásvédelem
  CASE
    WHEN visible_light_reflection_ext >= 45 THEN 'Erős'
    WHEN visible_light_reflection_ext >= 25 THEN 'Közepes'
    WHEN visible_light_reflection_ext >= 15 THEN 'Enyhe'
    ELSE 'Nincs'
  END AS privacy_level,

  final_score

FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY family
      ORDER BY final_score DESC
    ) AS rn
  FROM scored_products
)

WHERE rn = 1
ORDER BY exact_match DESC, final_score DESC
LIMIT 5