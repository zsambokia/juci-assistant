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
    @privacy_required AS privacy_required
),

filtered_products AS (
  SELECT
    p.*,
    r.heat_comfort_score,
    r.privacy_score,
    r.natural_light_score,
    r.visible_light_reflection_ext,
    w.*
  FROM `folias-juci.assistant.product_ranking` r
  JOIN `folias-juci.assistant.products` p
    ON r.product_id = p.product_id
  JOIN `folias-juci.assistant.product_glass_compatibility` g
    ON p.product_id = g.product_id
  CROSS JOIN wizard_input w
  WHERE
    p.surface = w.surface

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

    AND (
      w.reflectivity_preference = 'any'
      OR (
        w.reflectivity_preference = 'mirror'
        AND r.visible_light_reflection_ext >= 15
      )
      OR (
        w.reflectivity_preference = 'neutral'
        AND r.visible_light_reflection_ext < 15
      )
    )

    AND (
      w.privacy_required = FALSE
      OR r.privacy_score >= 20
    )
),

scored_products AS (
  SELECT
    *,
    (
      heat_comfort_score * heat_priority +
      privacy_score * privacy_priority +
      natural_light_score * light_priority
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
ORDER BY final_score DESC
LIMIT 5