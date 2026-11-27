-- =============================================================================
-- CivicFlow — Dhaka competition demo seed (Supabase SQL Editor)
-- =============================================================================
-- Paste the WHOLE file into Supabase SQL Editor and click "Run".
-- Runs as the SQL Editor role (postgres), so RLS is bypassed for this script.
-- Requires all Alembic migrations through 0026_weather_intelligence to be applied.
--
-- Idempotent: all primary keys are deterministic UUIDs; re-running refreshes the
-- same demo rows instead of creating duplicates. No auth.users are created and
-- no passwords/credentials are written. Existing real incidents are untouched
-- unless their title/description/address matches an obvious junk pattern.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 0. Preflight
-- -----------------------------------------------------------------------------
DO $preflight$
BEGIN
    IF to_regclass('public.incidents') IS NULL
       OR to_regclass('public.profiles') IS NULL
       OR to_regclass('public.infrastructure_assets') IS NULL THEN
        RAISE EXCEPTION
            'CivicFlow schema is missing. Apply all Alembic migrations first.';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.profiles WHERE is_active) THEN
        RAISE EXCEPTION
            'No active public.profiles row exists. Sign in once through the app '
            'so Supabase Auth provisions a profile, then re-run this script.';
    END IF;
END
$preflight$;

-- -----------------------------------------------------------------------------
-- 0b. Normalize incident status CHECK constraints
-- -----------------------------------------------------------------------------
-- Live databases may retain an older, hashed-name CHECK that still rejects
-- VERIFIED/ASSIGNED/... even though migration 0025 replaced the known names.
-- Drop every status-only CHECK and re-add one with the full current value set.
DO $fix_status_checks$
DECLARE
    r record;
    v_statuses text := $vals$'OPEN', 'VERIFIED', 'ASSIGNED', 'ACCEPTED', 'ACKNOWLEDGED', 'IN_PROGRESS', 'COMPLETION_SUBMITTED', 'VERIFIED_COMPLETED', 'RESOLVED', 'CLOSED'$vals$;
BEGIN
    FOR r IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.incidents'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) ILIKE '%status%'
          AND pg_get_constraintdef(oid) NOT ILIKE '%resolved_at%'
    LOOP
        EXECUTE format('ALTER TABLE public.incidents DROP CONSTRAINT %I', r.conname);
    END LOOP;
    ALTER TABLE public.incidents DROP CONSTRAINT IF EXISTS ck_incidents_status_values;
    EXECUTE format(
        'ALTER TABLE public.incidents ADD CONSTRAINT ck_incidents_status_values '
        'CHECK (status IN (%s))', v_statuses
    );

    FOR r IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.incident_status_events'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) ILIKE '%to_status%'
          AND pg_get_constraintdef(oid) NOT ILIKE '%<>%'
    LOOP
        EXECUTE format('ALTER TABLE public.incident_status_events DROP CONSTRAINT %I', r.conname);
    END LOOP;
    ALTER TABLE public.incident_status_events DROP CONSTRAINT IF EXISTS ck_incident_status_events_to_values;
    EXECUTE format(
        'ALTER TABLE public.incident_status_events ADD CONSTRAINT ck_incident_status_events_to_values '
        'CHECK (to_status IN (%s))', v_statuses
    );

    FOR r IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.incident_status_events'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) ILIKE '%from_status%'
          AND pg_get_constraintdef(oid) NOT ILIKE '%<>%'
    LOOP
        EXECUTE format('ALTER TABLE public.incident_status_events DROP CONSTRAINT %I', r.conname);
    END LOOP;
    ALTER TABLE public.incident_status_events DROP CONSTRAINT IF EXISTS ck_incident_status_events_from_values;
    EXECUTE format(
        'ALTER TABLE public.incident_status_events ADD CONSTRAINT ck_incident_status_events_from_values '
        'CHECK (from_status IS NULL OR from_status IN (%s))', v_statuses
    );
END
$fix_status_checks$;


-- -----------------------------------------------------------------------------
-- 1. Clean up garbage test data
-- -----------------------------------------------------------------------------
CREATE TEMP TABLE _cf_junk ON COMMIT DROP AS
SELECT id
FROM public.incidents
WHERE title ~* '(sdgdsgfdsg|asdf|qwerty|lorem ipsum|test[ _-]?incident|^test$|^dummy$|^sample$)'
   OR COALESCE(description, '') ~* '(sdgdsgfdsg|asdf|qwerty|lorem ipsum)'
   OR COALESCE(address, '')     ~* '(sdgdsgfdsg|asdf|qwerty)';

-- Child rows first (FKs to incidents are RESTRICT in several places).
DELETE FROM public.incident_assignment_events AS e
USING _cf_junk AS j
WHERE e.assignment_id IN (
    SELECT a.id FROM public.incident_assignments AS a WHERE a.incident_id = j.id
);

DELETE FROM public.incident_assignments AS a
USING _cf_junk AS j
WHERE a.incident_id = j.id;

DELETE FROM public.incident_evidence AS e
USING _cf_junk AS j
WHERE e.incident_id = j.id;

DELETE FROM public.incident_status_events AS s
USING _cf_junk AS j
WHERE s.incident_id = j.id;

DELETE FROM public.incident_cluster_members AS m
USING _cf_junk AS j
WHERE m.incident_id = j.id;

DELETE FROM public.incident_relationships AS r
USING _cf_junk AS j
WHERE r.incident_a_id = j.id OR r.incident_b_id = j.id;

DELETE FROM public.risk_assessments AS ra
USING _cf_junk AS j
WHERE ra.entity_type = 'INCIDENT' AND ra.entity_id = j.id;

-- Optional tables from later phases: only touch them if they exist.
DO $optional_cleanup$
BEGIN
    IF to_regclass('public.weather_assessments') IS NOT NULL THEN
        EXECUTE '
            DELETE FROM public.weather_assessments AS w
            USING _cf_junk AS j
            WHERE w.incident_id = j.id';
    END IF;
    IF to_regclass('public.ground_truth_records') IS NOT NULL THEN
        EXECUTE '
            DELETE FROM public.ground_truth_records AS g
            USING _cf_junk AS j
            WHERE g.incident_id = j.id';
    END IF;
    IF to_regclass('public.correlation_candidates') IS NOT NULL THEN
        EXECUTE '
            DELETE FROM public.correlation_candidates AS c
            USING _cf_junk AS j
            WHERE c.source_incident_id = j.id OR c.target_incident_id = j.id';
    END IF;
    IF to_regclass('public.pilot_incident_events') IS NOT NULL THEN
        EXECUTE '
            DELETE FROM public.pilot_incident_events AS p
            USING _cf_junk AS j
            WHERE p.incident_id = j.id';
    END IF;
END
$optional_cleanup$;

DELETE FROM public.incidents AS i
USING _cf_junk AS j
WHERE i.id = j.id;

-- Remove clusters left empty by the cleanup above.
DELETE FROM public.incident_clusters AS c
WHERE NOT EXISTS (
    SELECT 1 FROM public.incident_cluster_members AS m WHERE m.cluster_id = c.id
);

-- Remove the generic app-level dev seed assets (explicitly marked by seed.py)
-- so the map only shows the Dhaka cluster. Real/imported assets are untouched.
DELETE FROM public.dependency_edges AS d
WHERE d.source_asset_id IN (
        SELECT id FROM public.infrastructure_assets WHERE metadata ->> 'seed' = 'true'
      )
   OR d.target_asset_id IN (
        SELECT id FROM public.infrastructure_assets WHERE metadata ->> 'seed' = 'true'
      );

DELETE FROM public.infrastructure_assets
WHERE metadata ->> 'seed' = 'true';


-- -----------------------------------------------------------------------------
-- 2. Shared context: a real reporter profile and an approver/admin profile
-- -----------------------------------------------------------------------------
CREATE TEMP TABLE _cf_ctx ON COMMIT DROP AS
SELECT
    r.id AS reporter_id,
    COALESCE(a.id, r.id) AS actor_id
FROM (
    SELECT id FROM public.profiles
    WHERE is_active
    ORDER BY (role = 'CITIZEN') DESC, created_at
    LIMIT 1
) AS r
LEFT JOIN LATERAL (
    SELECT id FROM public.profiles
    WHERE role = 'ADMIN' AND is_active
    ORDER BY created_at
    LIMIT 1
) AS a ON true;

-- Departments: reuse existing rows with the same lower(name).
CREATE TEMP TABLE _cf_depts ON COMMIT DROP AS
WITH proposed (dept_key, name, description, id) AS (
    VALUES
        ('public works', 'Public Works',
         'Roads, civic facilities, and public infrastructure.',
         '82c4cbcd-250b-58a7-8b84-5a8bd92ee297'::uuid),
        ('drainage & sanitation', 'Drainage & Sanitation',
         'Drainage, waste, and sanitation response.',
         '0a3d048c-6956-5fde-8eaa-1047a63a3056'::uuid),
        ('emergency services', 'Emergency Services',
         'Emergency coordination and critical facilities.',
         'f3b31cdf-c304-58c6-9169-a7ec6d1559c1'::uuid)
),
ins AS (
    INSERT INTO public.departments (id, name, description, is_active)
    SELECT id, name, description, true FROM proposed
    ON CONFLICT DO NOTHING
    RETURNING lower(name) AS dept_key, id
)
SELECT p.dept_key, COALESCE(i.id, d.id) AS id
FROM proposed AS p
LEFT JOIN ins AS i ON i.dept_key = p.dept_key
LEFT JOIN public.departments AS d ON lower(d.name) = p.dept_key;


-- -----------------------------------------------------------------------------
-- 3. Five interconnected Dhaka incidents (Mirpur-10 / Kazipara / Agargaon)
-- -----------------------------------------------------------------------------
INSERT INTO public.incidents (
    id, title, description, category, severity, status,
    location, address, reporter_id, assigned_department_id, created_at
)
SELECT
    v.id, v.title, v.description, v.category, v.severity, v.status,
    ST_SetSRID(ST_MakePoint(v.lon, v.lat), 4326)::geography,
    v.address,
    c.reporter_id,
    (SELECT d.id FROM _cf_depts AS d WHERE d.dept_key = v.dept_key),
    CURRENT_TIMESTAMP - v.age
FROM (
    VALUES
        (
            '65449c49-8788-5782-8a90-669dbd09601e'::uuid,
            'Severe Storm Drain Blockage at Mirpur-10 Roundabout',
            'Main storm drain inlet beside the Mirpur-10 arterial roundabout is completely blocked by silt and debris. Water cannot enter the trunk line, so the upstream cartway is flooding. Suspected root cause of the downstream waterlogging along Begum Rokeya Sarani.',
            'DRAINAGE', 'CRITICAL', 'OPEN',
            90.3609::double precision, 23.8281::double precision,
            'Mirpur-10 Roundabout, Mirpur Road, Dhaka 1206',
            'drainage & sanitation', interval '45 minutes'
        ),
        (
            '1e8d2a12-d20e-56b4-8f85-09706d01d98e'::uuid,
            'Flash Waterlogging Submerging Begum Rokeya Sarani',
            'Approximately 400 m of the Begum Rokeya Sarani carriageway is under 20-30 cm of rainwater following the blocked upstream drain. Traffic is crawling and pedestrian access to adjacent clinics is affected.',
            'ROADS', 'HIGH', 'OPEN',
            90.3702::double precision, 23.8231::double precision,
            'Begum Rokeya Sarani, Kazipara, Mirpur, Dhaka 1216',
            'drainage & sanitation', interval '2 hours'
        ),
        (
            'f7ccbdc0-9863-57b7-a018-60885f702e76'::uuid,
            'Ambulance Route Blocked Near Al-Helal Specialized Hospital',
            'The only practical ambulance approach to Al-Helal Specialized Hospital is cut off by the flooded segment of Begum Rokeya Sarani. Emergency access is at risk; a diverted route via the hospital rear lane is needed until the water recedes.',
            'PUBLIC_SAFETY', 'CRITICAL', 'VERIFIED',
            90.3636::double precision, 23.8263::double precision,
            'Al-Helal Specialized Hospital, Mirpur-10, Dhaka 1216',
            'emergency services', interval '3 hours'
        ),
        (
            'b4c4e204-e5e0-57e5-9955-24f3469195c4'::uuid,
            'Uncollected Solid Waste Choking Secondary Canal at Kazipara',
            'Household waste and plastic packaging have accumulated at the Kazipara secondary canal mouth, reducing its flow capacity by an estimated 60 percent. This compounds flooding on the downstream Begum Rokeya Sarani segment.',
            'SANITATION', 'MEDIUM', 'OPEN',
            90.3684::double precision, 23.8258::double precision,
            'Secondary Canal, Kazipara, Mirpur, Dhaka 1216',
            'drainage & sanitation', interval '5 hours'
        ),
        (
            '77aa6e3e-82e3-548a-8cbd-2d958f03fc90'::uuid,
            'Deep Asphalt Sinkhole Near Agargaon Metro Station',
            'A 1.2 m asphalt sinkhole has opened on the access road to Agargaon Metro Station. Commuters are avoiding the lane and the depression is filling with rainwater, creating a collision and drainage hazard.',
            'ROADS', 'MEDIUM', 'OPEN',
            90.3810::double precision, 23.8168::double precision,
            'Agargaon Metro Station Access Road, Dhaka 1207',
            'public works', interval '7 hours'
        )
) AS v (
    id, title, description, category, severity, status,
    lon, lat, address, dept_key, age
)
CROSS JOIN _cf_ctx AS c
ON CONFLICT (id) DO UPDATE SET
    title                 = EXCLUDED.title,
    description           = EXCLUDED.description,
    category              = EXCLUDED.category,
    severity              = EXCLUDED.severity,
    status                = EXCLUDED.status,
    location              = EXCLUDED.location,
    address               = EXCLUDED.address,
    reporter_id           = EXCLUDED.reporter_id,
    assigned_department_id = EXCLUDED.assigned_department_id;

-- Lifecycle event for the VERIFIED incident.
INSERT INTO public.incident_status_events (
    id, incident_id, actor_id, from_status, to_status, note, created_at
)
SELECT
    '03bc0cf7-503e-5107-8c5e-22542c7e2ec5'::uuid,
    i.id,
    c.actor_id,
    'OPEN',
    'VERIFIED',
    'Verified against field report: ambulance access to the hospital is obstructed.',
    CURRENT_TIMESTAMP - interval '2 hours 30 minutes'
FROM public.incidents AS i
CROSS JOIN _cf_ctx AS c
WHERE i.id = 'f7ccbdc0-9863-57b7-a018-60885f702e76'::uuid
ON CONFLICT (id) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 4. Nearby critical infrastructure and dependency graph
-- -----------------------------------------------------------------------------
INSERT INTO public.infrastructure_assets (
    id, name, asset_type, location, description,
    criticality_score, is_active, metadata
)
VALUES
    (
        '408290a9-c389-5360-979a-3c0556764bd0'::uuid,
        'Mirpur-10 Storm Drain Trunk', 'DRAIN',
        ST_GeomFromText('LINESTRING(90.3594 23.8290, 90.3630 23.8272, 90.3705 23.8228)', 4326),
        'Primary drainage trunk carrying flow from Mirpur-10 east towards Kazipara.',
        9.20, true,
        '{"seed":"dhaka-demo","osm_tag":"drain","capacity_class":"primary"}'::jsonb
    ),
    (
        '31ad7e70-aefc-5a2e-a15a-f4655f9f28bc'::uuid,
        'Begum Rokeya Sarani (Arterial)', 'ROAD',
        ST_GeomFromText('LINESTRING(90.3590 23.8288, 90.3702 23.8231, 90.3830 23.8170)', 4326),
        'Major east-west arterial linking Mirpur-10 with Agargaon metro station.',
        9.60, true,
        '{"seed":"dhaka-demo","osm_tag":"road","lanes":4}'::jsonb
    ),
    (
        'd5869a70-06f5-5ac6-b1ba-c194891d02ad'::uuid,
        'Al-Helal Specialized Hospital', 'HOSPITAL',
        ST_GeomFromText('POINT(90.3636 23.8263)', 4326),
        'Specialized hospital serving Mirpur-10; dependent on the arterial road for ambulance access.',
        10.00, true,
        '{"seed":"dhaka-demo","category":"hospital","emergency_access":true}'::jsonb
    ),
    (
        '10b8c39c-961e-5a9f-9e53-10e060d26c08'::uuid,
        'Mirpur-10 Metro Station (MRT Line 6)', 'OTHER',
        ST_GeomFromText('POINT(90.3606 23.8284)', 4326),
        'MRT Line 6 station at Mirpur-10; high passenger interchange beside the blocked drain.',
        8.80, true,
        '{"seed":"dhaka-demo","category":"metro_station","line":"MRT-6"}'::jsonb
    ),
    (
        '7bb71612-4a2d-5c9f-a48b-38bab2c7ba25'::uuid,
        'Kazipara Secondary Canal', 'DRAIN',
        ST_GeomFromText('LINESTRING(90.3660 23.8262, 90.3710 23.8246)', 4326),
        'Secondary canal receiving waste discharge and feeding the Mirpur-10 trunk.',
        7.50, true,
        '{"seed":"dhaka-demo","osm_tag":"canal","capacity_class":"secondary"}'::jsonb
    ),
    (
        '19965638-ccae-5562-b604-15d929d178f7'::uuid,
        'Agargaon Metro Station', 'OTHER',
        ST_GeomFromText('POINT(90.3810 23.8168)', 4326),
        'MRT Line 6 station and major commuter access point at Agargaon.',
        9.10, true,
        '{"seed":"dhaka-demo","category":"metro_station","line":"MRT-6"}'::jsonb
    )
ON CONFLICT (id) DO UPDATE SET
    name              = EXCLUDED.name,
    asset_type        = EXCLUDED.asset_type,
    location          = EXCLUDED.location,
    description       = EXCLUDED.description,
    criticality_score = EXCLUDED.criticality_score,
    is_active         = EXCLUDED.is_active,
    metadata          = EXCLUDED.metadata,
    updated_at        = CURRENT_TIMESTAMP;

INSERT INTO public.dependency_edges (
    id, source_asset_id, target_asset_id, dependency_type, strength, description
)
VALUES
    (
        '3d939399-8620-598f-b285-d2a17a864cc5'::uuid,
        '408290a9-c389-5360-979a-3c0556764bd0'::uuid,
        '31ad7e70-aefc-5a2e-a15a-f4655f9f28bc'::uuid,
        'PROTECTS', 0.92,
        'The drain trunk protects the arterial from surface flooding.'
    ),
    (
        'de087add-a489-539d-b1b3-c70eccdc0eee'::uuid,
        '31ad7e70-aefc-5a2e-a15a-f4655f9f28bc'::uuid,
        'd5869a70-06f5-5ac6-b1ba-c194891d02ad'::uuid,
        'SERVES', 0.95,
        'Begum Rokeya Sarani is the primary ambulance access route to the hospital.'
    ),
    (
        'bf072c5b-796d-5605-b08f-f5728a5d4297'::uuid,
        'd5869a70-06f5-5ac6-b1ba-c194891d02ad'::uuid,
        '31ad7e70-aefc-5a2e-a15a-f4655f9f28bc'::uuid,
        'DEPENDS_ON', 0.88,
        'Hospital emergency operations depend on the arterial staying passable.'
    ),
    (
        '8d83cd35-f227-580f-b39e-8327359f3ae1'::uuid,
        '7bb71612-4a2d-5c9f-a48b-38bab2c7ba25'::uuid,
        '408290a9-c389-5360-979a-3c0556764bd0'::uuid,
        'FEEDS', 0.78,
        'The Kazipara secondary canal discharges into the Mirpur-10 trunk.'
    ),
    (
        '30b36874-72a5-5788-b4ad-5535031004f5'::uuid,
        '10b8c39c-961e-5a9f-9e53-10e060d26c08'::uuid,
        '31ad7e70-aefc-5a2e-a15a-f4655f9f28bc'::uuid,
        'ADJACENT_TO', 0.65,
        'Mirpur-10 metro station sits directly beside the arterial drainage blockage.'
    ),
    (
        '91280b78-9c5c-5301-ac36-9b71c93f71c4'::uuid,
        '10b8c39c-961e-5a9f-9e53-10e060d26c08'::uuid,
        'd5869a70-06f5-5ac6-b1ba-c194891d02ad'::uuid,
        'SERVES', 0.70,
        'Metro station serves hospital staff and visitors in the Mirpur-10 cluster.'
    ),
    (
        'e240de33-e7bf-55d8-bbf6-459c0b1f8c5f'::uuid,
        '408290a9-c389-5360-979a-3c0556764bd0'::uuid,
        '7bb71612-4a2d-5c9f-a48b-38bab2c7ba25'::uuid,
        'FEEDS', 0.60,
        'Backflow connection makes the secondary canal sensitive to trunk blockage.'
    )
ON CONFLICT (id) DO UPDATE SET
    dependency_type = EXCLUDED.dependency_type,
    strength        = EXCLUDED.strength,
    description     = EXCLUDED.description;


-- -----------------------------------------------------------------------------
-- 5. Confirmed incident relationships (Incident Intelligence cascade paths)
-- -----------------------------------------------------------------------------
INSERT INTO public.incident_relationships (
    id, incident_a_id, incident_b_id, relationship_type, status,
    confidence, signals, note, reviewed_by, reviewed_at
)
SELECT
    v.id,
    v.a_id,
    v.b_id,
    v.relationship_type,
    'CONFIRMED',
    v.confidence,
    v.signals::jsonb,
    v.note,
    c.actor_id,
    CURRENT_TIMESTAMP - interval '1 hour'
FROM (
    VALUES
        (
            '27777afe-0655-5498-b37a-f0c7504733fd'::uuid,
            '65449c49-8788-5782-8a90-669dbd09601e'::uuid,
            '1e8d2a12-d20e-56b4-8f85-09706d01d98e'::uuid,
            'RELATED', 0.96,
            '{"spatial_proximity_m":950,"category_link":"DRAINAGE->ROADS","hydrology":"downstream"}',
            'Blocked Mirpur-10 drain is the upstream cause of the waterlogged arterial.'
        ),
        (
            'c569e1aa-6315-5187-8cc0-56f027ade51c'::uuid,
            '1e8d2a12-d20e-56b4-8f85-09706d01d98e'::uuid,
            'f7ccbdc0-9863-57b7-a018-60885f702e76'::uuid,
            'RELATED', 0.93,
            '{"spatial_proximity_m":700,"shared_asset":"Begum Rokeya Sarani","impact":"emergency_access"}',
            'Flooded road segment blocks the hospital ambulance approach.'
        ),
        (
            '6d716fb8-1b9e-5e7c-8b25-ee8b7edeca34'::uuid,
            '65449c49-8788-5782-8a90-669dbd09601e'::uuid,
            'f7ccbdc0-9863-57b7-a018-60885f702e76'::uuid,
            'CONTEXT', 0.86,
            '{"shared_asset":"Mirpur-10 Storm Drain Trunk","severity":"CRITICAL"}',
            'Critical infrastructure risk links the drain fault to emergency access.'
        ),
        (
            '21c65bd1-18a5-5a77-8e1d-c1c8b3d53138'::uuid,
            'b4c4e204-e5e0-57e5-9955-24f3469195c4'::uuid,
            '1e8d2a12-d20e-56b4-8f85-09706d01d98e'::uuid,
            'RELATED', 0.81,
            '{"shared_asset":"Kazipara Secondary Canal","capacity_loss_pct":60}',
            'Waste-choked canal reduces capacity and aggravates downstream flooding.'
        ),
        (
            'b7d67648-c764-54ca-a6a4-01ca7211d527'::uuid,
            '77aa6e3e-82e3-548a-8cbd-2d958f03fc90'::uuid,
            '1e8d2a12-d20e-56b4-8f85-09706d01d98e'::uuid,
            'CONTEXT', 0.67,
            '{"shared_asset":"Begum Rokeya Sarani","distance_m":1900}',
            'Sinkhole on the same arterial contributes to localized drainage failure.'
        )
) AS v (id, a_id, b_id, relationship_type, confidence, signals, note)
CROSS JOIN _cf_ctx AS c
ON CONFLICT (id) DO UPDATE SET
    relationship_type = EXCLUDED.relationship_type,
    status            = EXCLUDED.status,
    confidence        = EXCLUDED.confidence,
    signals           = EXCLUDED.signals,
    note              = EXCLUDED.note,
    updated_at        = CURRENT_TIMESTAMP;


-- -----------------------------------------------------------------------------
-- 6. Spatial cluster for the dashboard/map cluster view
-- -----------------------------------------------------------------------------
INSERT INTO public.incident_clusters (id, category, centroid, status)
VALUES (
    'e652a25d-0203-5140-90f8-fc032bde94e2'::uuid,
    'DRAINAGE',
    ST_SetSRID(ST_MakePoint(90.3686, 23.8224), 4326)::geography,
    'ACTIVE'
)
ON CONFLICT (id) DO UPDATE SET
    category  = EXCLUDED.category,
    centroid  = EXCLUDED.centroid,
    status    = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO public.incident_cluster_members (id, cluster_id, incident_id, added_at)
SELECT v.id, k.cluster_id, v.incident_id, CURRENT_TIMESTAMP - interval '1 hour'
FROM (
    VALUES
        ('8bac028c-c8ef-5d79-9a73-034471b94495'::uuid, '65449c49-8788-5782-8a90-669dbd09601e'::uuid),
        ('442dc60b-58e4-5a8a-a207-d2e7874d5210'::uuid, '1e8d2a12-d20e-56b4-8f85-09706d01d98e'::uuid),
        ('dc386fd7-61b9-5957-8453-018039818cd1'::uuid, 'f7ccbdc0-9863-57b7-a018-60885f702e76'::uuid),
        ('554fa691-d51e-5c8b-9cf7-a31d0b33d9f7'::uuid, 'b4c4e204-e5e0-57e5-9955-24f3469195c4'::uuid),
        ('a69896e4-7cbc-59f3-91c9-d6f58d3254b9'::uuid, '77aa6e3e-82e3-548a-8cbd-2d958f03fc90'::uuid)
) AS v (id, incident_id)
CROSS JOIN (SELECT 'e652a25d-0203-5140-90f8-fc032bde94e2'::uuid AS cluster_id) AS k
WHERE NOT EXISTS (
    SELECT 1 FROM public.incident_cluster_members AS m WHERE m.incident_id = v.incident_id
)
ON CONFLICT (id) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 7. Explainable risk assessments for the cascade demo
-- -----------------------------------------------------------------------------
INSERT INTO public.risk_assessments (
    id, entity_type, entity_id, score, risk_level, model_version, explanation, assessed_at
)
VALUES
    (
        'dcb44854-03ab-52bc-b113-9b03c03c346c'::uuid, 'INCIDENT',
        '65449c49-8788-5782-8a90-669dbd09601e'::uuid, 91.50, 'EXTREME', 'demo-dhaka-v1',
        '{"drivers":["critical severity","drain trunk exposed","upstream of arterial"],"confidence":0.92}'::jsonb,
        CURRENT_TIMESTAMP - interval '30 minutes'
    ),
    (
        'ae90b431-131e-5e2e-bc72-cada52fcf868'::uuid, 'INCIDENT',
        '1e8d2a12-d20e-56b4-8f85-09706d01d98e'::uuid, 84.00, 'SEVERE', 'demo-dhaka-v1',
        '{"drivers":["high severity","400m carriageway submerged","two confirmed upstream links"],"confidence":0.89}'::jsonb,
        CURRENT_TIMESTAMP - interval '1 hour'
    ),
    (
        '61cdc176-72ae-5f82-99fe-5203bd4d297d'::uuid, 'INCIDENT',
        'f7ccbdc0-9863-57b7-a018-60885f702e76'::uuid, 95.00, 'EXTREME', 'demo-dhaka-v1',
        '{"drivers":["critical severity","hospital exposure","verified"],"confidence":0.95}'::jsonb,
        CURRENT_TIMESTAMP - interval '2 hours'
    ),
    (
        'bc8538d1-794a-553b-847f-fecc3fd6daf5'::uuid, 'INCIDENT',
        'b4c4e204-e5e0-57e5-9955-24f3469195c4'::uuid, 58.00, 'HIGH', 'demo-dhaka-v1',
        '{"drivers":["canal capacity loss","downstream flood contribution"],"confidence":0.78}'::jsonb,
        CURRENT_TIMESTAMP - interval '4 hours'
    ),
    (
        '3d2c5e11-897c-5567-8255-9ea7a67699f6'::uuid, 'INCIDENT',
        '77aa6e3e-82e3-548a-8cbd-2d958f03fc90'::uuid, 54.00, 'MODERATE', 'demo-dhaka-v1',
        '{"drivers":["metro access road","rainwater-filled depression"],"confidence":0.74}'::jsonb,
        CURRENT_TIMESTAMP - interval '6 hours'
    ),
    (
        'c96bb09b-1c06-5d20-b8d4-f062b4348be3'::uuid, 'INFRASTRUCTURE_ASSET',
        'd5869a70-06f5-5ac6-b1ba-c194891d02ad'::uuid, 93.00, 'EXTREME', 'demo-dhaka-v1',
        '{"drivers":["criticality 10/10","ambulance route blocked"],"confidence":0.93}'::jsonb,
        CURRENT_TIMESTAMP - interval '2 hours'
    ),
    (
        '8cede7ad-d875-5187-8b59-50969c4f5e63'::uuid, 'INFRASTRUCTURE_ASSET',
        '408290a9-c389-5360-979a-3c0556764bd0'::uuid, 89.00, 'SEVERE', 'demo-dhaka-v1',
        '{"drivers":["primary trunk","blocked inlet","flood backflow"],"confidence":0.88}'::jsonb,
        CURRENT_TIMESTAMP - interval '45 minutes'
    ),
    (
        '0c7c2139-33e3-57c5-bec4-2fbbbdb67a9c'::uuid, 'INFRASTRUCTURE_ASSET',
        '31ad7e70-aefc-5a2e-a15a-f4655f9f28bc'::uuid, 86.00, 'SEVERE', 'demo-dhaka-v1',
        '{"drivers":["4-lane arterial","flooded segment","hospital access"],"confidence":0.86}'::jsonb,
        CURRENT_TIMESTAMP - interval '2 hours'
    )
ON CONFLICT (id) DO UPDATE SET
    score        = EXCLUDED.score,
    risk_level   = EXCLUDED.risk_level,
    explanation  = EXCLUDED.explanation,
    assessed_at  = EXCLUDED.assessed_at;


-- -----------------------------------------------------------------------------
-- 8. Heavy rainfall decision scenario (Incident Intelligence -> simulation)
-- -----------------------------------------------------------------------------
INSERT INTO public.decision_scenarios (
    id, name, description, hazard_type, parameters,
    horizon_minutes, budget_limit, resolution, risk_window_hours,
    status, created_by
)
SELECT
    'aea57bff-dcfa-5152-b952-b52e1e786edf'::uuid,
    'Heavy Rainfall — Mirpur-10 to Agargaon Cascading Flood',
    'Planning-only scenario: a 120 mm/6 h rainfall event overloading the Mirpur-10 drain, submerging Begum Rokeya Sarani and blocking hospital emergency access.',
    'FLOOD',
    '{"context":"BD-DHAKA","rainfall_mm":120,"duration_hours":6,"cluster":"Mirpur-10/Kazipara/Agargaon","planning_only":true}'::jsonb,
    360, 250000.00, 8, 168,
    'DRAFT',
    c.actor_id
FROM _cf_ctx AS c
ON CONFLICT (id) DO UPDATE SET
    name              = EXCLUDED.name,
    description       = EXCLUDED.description,
    hazard_type       = EXCLUDED.hazard_type,
    parameters        = EXCLUDED.parameters,
    horizon_minutes   = EXCLUDED.horizon_minutes,
    budget_limit      = EXCLUDED.budget_limit,
    resolution        = EXCLUDED.resolution,
    risk_window_hours = EXCLUDED.risk_window_hours,
    status            = EXCLUDED.status,
    created_by        = EXCLUDED.created_by,
    updated_at        = CURRENT_TIMESTAMP;

INSERT INTO public.response_resources (
    id, name, resource_type, unit, quantity_available, availability_status,
    availability_source, available_as_of, allocation_mode, department_id,
    is_active, metadata_json
)
SELECT
    v.id, v.name, v.resource_type, v.unit, v.quantity_available,
    v.availability_status, 'Demo room planning assumption (not a real inventory)',
    CURRENT_TIMESTAMP - interval '1 hour', v.allocation_mode,
    (SELECT d.id FROM _cf_depts AS d WHERE d.dept_key = v.dept_key),
    true, '{"seed":"dhaka-demo","planning_assumption":true}'::jsonb
FROM (
    VALUES
        ('169bc7f8-2ed1-59e0-b8eb-8fe5f1807c48'::uuid, 'Drainage field crew', 'PERSONNEL', 'crew', 3::numeric, 'AVAILABLE', 'SHARED_CAPACITY', 'drainage & sanitation'),
        ('e985728d-b926-5fac-87f0-5259f6257127'::uuid, 'Mobile pump truck', 'VEHICLE', 'truck', 2::numeric, 'AVAILABLE', 'CONSUMABLE', 'drainage & sanitation'),
        ('6a22e53e-132a-549f-ac8d-d1cc22b23c00'::uuid, 'Ambulance support unit', 'VEHICLE', 'vehicle', 2::numeric, 'LIMITED', 'SHARED_CAPACITY', 'emergency services')
) AS v (id, name, resource_type, unit, quantity_available, availability_status, allocation_mode, dept_key)
ON CONFLICT (id) DO UPDATE SET
    name                = EXCLUDED.name,
    quantity_available  = EXCLUDED.quantity_available,
    availability_status = EXCLUDED.availability_status,
    department_id       = EXCLUDED.department_id,
    updated_at          = CURRENT_TIMESTAMP;

INSERT INTO public.decision_actions (
    id, scenario_id, title, description, action_type,
    target_h3_cell_id, target_asset_id, department_id,
    priority, earliest_start_minutes, duration_minutes,
    expected_risk_reduction, estimated_cost, depends_on_action_id,
    is_active, assumptions
)
SELECT
    v.id,
    'aea57bff-dcfa-5152-b952-b52e1e786edf'::uuid,
    v.title, v.description, v.action_type,
    v.cell,
    (SELECT a.id FROM public.infrastructure_assets AS a WHERE a.id = v.asset_id),
    (SELECT d.id FROM _cf_depts AS d WHERE d.dept_key = v.dept_key),
    v.priority, v.earliest, v.duration, v.reduction, v.cost,
    v.depends_on,
    true,
    '{"seed":"dhaka-demo","planning_only":true}'::jsonb
FROM (
    VALUES
        (
            'd55bbb9c-1dda-577f-adcd-1b6f853f9b06'::uuid,
            'Clear blocked Mirpur-10 storm drain inlet',
            'Manual debris removal and silt excavation at the main inlet before pumping.',
            'CLEAN', '883cf10e9dfffff',
            '408290a9-c389-5360-979a-3c0556764bd0'::uuid, 'drainage & sanitation',
            1, 0, 120, 34.00::numeric, 45000.00::numeric, NULL::uuid
        ),
        (
            'b0d93e06-e108-5ec7-9519-7c5b0e3808ff'::uuid,
            'Deploy mobile pumps on Begum Rokeya Sarani',
            'Remove standing water from the 400 m submerged carriageway once the inlet is cleared.',
            'DISPATCH', '883cf10e95fffff',
            '31ad7e70-aefc-5a2e-a15a-f4655f9f28bc'::uuid, 'drainage & sanitation',
            2, 60, 180, 27.00::numeric, 62000.00::numeric,
            'd55bbb9c-1dda-577f-adcd-1b6f853f9b06'::uuid
        ),
        (
            'd44f6148-e32a-571a-8383-8207b4fa8eb2'::uuid,
            'Hold ambulance corridor for Al-Helal Hospital',
            'Keep a cleared lane and support unit available while the arterial is waterlogged.',
            'MEDICAL', '883cf10e9dfffff',
            'd5869a70-06f5-5ac6-b1ba-c194891d02ad'::uuid, 'emergency services',
            1, 0, 360, 22.00::numeric, 38000.00::numeric, NULL::uuid
        ),
        (
            '1abe07e6-6684-5988-8706-78c50ce3e5b1'::uuid,
            'Reopen arterial lane after water recedes',
            'Inspection and traffic marshalling on the affected Begum Rokeya Sarani segment.',
            'REPAIR', '883cf10e95fffff',
            '31ad7e70-aefc-5a2e-a15a-f4655f9f28bc'::uuid, 'public works',
            3, 180, 90, 16.00::numeric, 28000.00::numeric,
            'b0d93e06-e108-5ec7-9519-7c5b0e3808ff'::uuid
        ),
        (
            '8d2613fc-0d0a-56fc-9057-371297b4ada6'::uuid,
            'Clear Kazipara secondary canal mouth',
            'Remove solid waste at the canal mouth to restore 60 percent lost capacity.',
            'CLEAN', '883cf10e9dfffff',
            '7bb71612-4a2d-5c9f-a48b-38bab2c7ba25'::uuid, 'drainage & sanitation',
            2, 30, 150, 18.00::numeric, 33000.00::numeric, NULL::uuid
        ),
        (
            '79992870-8242-5510-be84-9510673b9508'::uuid,
            'Barricade and patch Agargaon sinkhole',
            'Install temporary barriers and begin asphalt repair at the metro access road.',
            'REPAIR', '883cf10e97fffff',
            '19965638-ccae-5562-b604-15d929d178f7'::uuid, 'public works',
            3, 60, 120, 12.00::numeric, 24000.00::numeric, NULL::uuid
        )
) AS v (id, title, description, action_type, cell, asset_id, dept_key,
        priority, earliest, duration, reduction, cost, depends_on)
ON CONFLICT (id) DO UPDATE SET
    title                 = EXCLUDED.title,
    action_type           = EXCLUDED.action_type,
    target_h3_cell_id     = EXCLUDED.target_h3_cell_id,
    target_asset_id       = EXCLUDED.target_asset_id,
    priority              = EXCLUDED.priority,
    expected_risk_reduction = EXCLUDED.expected_risk_reduction,
    estimated_cost        = EXCLUDED.estimated_cost,
    depends_on_action_id  = EXCLUDED.depends_on_action_id,
    updated_at            = CURRENT_TIMESTAMP;

INSERT INTO public.action_resource_requirements (id, action_id, resource_id, quantity_required)
VALUES
    ('e9da7bf9-1825-59b0-90d3-70050e9b2026'::uuid, 'd55bbb9c-1dda-577f-adcd-1b6f853f9b06'::uuid, '169bc7f8-2ed1-59e0-b8eb-8fe5f1807c48'::uuid, 2::numeric),
    ('5376db0e-d917-5d82-9fd4-1c24c76a29f8'::uuid, 'b0d93e06-e108-5ec7-9519-7c5b0e3808ff'::uuid, 'e985728d-b926-5fac-87f0-5259f6257127'::uuid, 2::numeric),
    ('eebe6117-5ff3-5c2e-9b05-fb7015717443'::uuid, 'd44f6148-e32a-571a-8383-8207b4fa8eb2'::uuid, '6a22e53e-132a-549f-ac8d-d1cc22b23c00'::uuid, 1::numeric),
    ('085ccb90-aa10-5005-9e2f-c65d82d66ef3'::uuid, '8d2613fc-0d0a-56fc-9057-371297b4ada6'::uuid, '169bc7f8-2ed1-59e0-b8eb-8fe5f1807c48'::uuid, 1::numeric),
    ('1b1f3e0e-d47c-5c6f-ba59-fd34640ec79a'::uuid, '79992870-8242-5510-be84-9510673b9508'::uuid, '169bc7f8-2ed1-59e0-b8eb-8fe5f1807c48'::uuid, 1::numeric)
ON CONFLICT (id) DO UPDATE SET quantity_required = EXCLUDED.quantity_required;


-- -----------------------------------------------------------------------------
-- 9. Ready workforce team (no auth.users created; reuses existing identities)
-- -----------------------------------------------------------------------------
CREATE TEMP TABLE _cf_workers ON COMMIT DROP AS
SELECT id, full_name, phone, email, rank_slot, created_at,
       row_number() OVER (ORDER BY rank_slot, created_at) AS slot
FROM (
    SELECT
        p.id, p.full_name, p.phone,
        COALESCE(u.email, '') AS email,
        p.created_at,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM public.worker_profiles AS wp
                WHERE wp.profile_id = p.id AND wp.status = 'ACTIVE'
            ) THEN 0
            WHEN p.role = 'WORKER' THEN 1
            WHEN COALESCE(u.email, '') ~* '(worker|field|team|demo|responder)' THEN 2
            ELSE 3
        END AS rank_slot
    FROM public.profiles AS p
    LEFT JOIN auth.users AS u ON u.id = p.id
    WHERE p.is_active
      AND p.role <> 'ADMIN'
    ORDER BY rank_slot, p.created_at
    LIMIT 3
) AS candidates;

-- Promote only the selected demo candidates. Existing work accounts keep WORKER.
UPDATE public.profiles AS p
SET role = 'WORKER', updated_at = CURRENT_TIMESTAMP
FROM _cf_workers AS w
WHERE p.id = w.id AND p.role <> 'WORKER';

DO $worker_check$
DECLARE
    n integer;
BEGIN
    SELECT count(*) INTO n FROM _cf_workers;
    IF n < 2 THEN
        RAISE WARNING
            'Only % reusable worker profile(s) found. Sign in with at least two '
            'non-admin demo accounts, then re-run to complete the workforce setup.', n;
    ELSE
        RAISE NOTICE 'Prepared % active approved demo field workers.', n;
    END IF;
END
$worker_check$;

INSERT INTO public.worker_applications (
    id, applicant_id, full_name, phone, email, specialization, department_id,
    service_area, address, experience, credentials_note, status,
    review_note, reviewer_id, reviewed_at
)
SELECT
    CASE w.slot
        WHEN 1 THEN '45bea524-e3fe-5609-acfa-f0aafb786ac1'::uuid
        WHEN 2 THEN 'a7164dc9-fd44-510f-b126-d4591bb6b530'::uuid
        ELSE '1afc1426-e4b3-5a69-94bc-2cad6e0efaaa'::uuid
    END,
    w.id, w.full_name, w.phone, NULLIF(w.email, ''),
    CASE w.slot
        WHEN 1 THEN 'Drainage & Waterlogging Specialist'
        WHEN 2 THEN 'Rapid Response & Road Safety Unit'
        ELSE 'Waste & Sanitation Response'
    END,
    (SELECT d.id FROM _cf_depts AS d
     WHERE d.dept_key = CASE w.slot WHEN 1 THEN 'drainage & sanitation'
                                    WHEN 2 THEN 'emergency services'
                                    ELSE 'public works' END),
    CASE w.slot
        WHEN 1 THEN 'Mirpur-10'
        WHEN 2 THEN 'Begum Rokeya Sarani'
        ELSE 'Kazipara'
    END,
    'Dhaka North City Corporation service zone',
    'Field response experience in Mirpur, Kazipara and Agargaon.',
    'Demo competition seed — approved by seed script.',
    'APPROVED',
    'Demo approval for competition walkthrough.',
    c.actor_id,
    CURRENT_TIMESTAMP - interval '2 days'
FROM _cf_workers AS w
CROSS JOIN _cf_ctx AS c
ON CONFLICT (applicant_id) DO UPDATE SET
    specialization = EXCLUDED.specialization,
    department_id  = EXCLUDED.department_id,
    service_area   = EXCLUDED.service_area,
    status         = 'APPROVED',
    review_note    = EXCLUDED.review_note,
    reviewer_id    = EXCLUDED.reviewer_id,
    reviewed_at    = EXCLUDED.reviewed_at,
    updated_at     = CURRENT_TIMESTAMP;

INSERT INTO public.worker_profiles (
    id, profile_id, application_id, specialization, department_id,
    service_area, status, approved_by, approved_at
)
SELECT
    CASE w.slot
        WHEN 1 THEN '4f3f9a8b-126a-5362-9680-1403caed072d'::uuid
        WHEN 2 THEN '735ac253-9cda-5cfc-bcf2-3986c8265920'::uuid
        ELSE '16b58177-c323-5789-9ed9-51d5a0932ba6'::uuid
    END,
    w.id,
    (SELECT a.id FROM public.worker_applications AS a WHERE a.applicant_id = w.id),
    CASE w.slot
        WHEN 1 THEN 'Drainage & Waterlogging Specialist'
        WHEN 2 THEN 'Rapid Response & Road Safety Unit'
        ELSE 'Waste & Sanitation Response'
    END,
    (SELECT d.id FROM _cf_depts AS d
     WHERE d.dept_key = CASE w.slot WHEN 1 THEN 'drainage & sanitation'
                                    WHEN 2 THEN 'emergency services'
                                    ELSE 'public works' END),
    CASE w.slot
        WHEN 1 THEN 'Mirpur-10'
        WHEN 2 THEN 'Begum Rokeya Sarani'
        ELSE 'Kazipara'
    END,
    'ACTIVE',
    c.actor_id,
    CURRENT_TIMESTAMP - interval '2 days'
FROM _cf_workers AS w
CROSS JOIN _cf_ctx AS c
ON CONFLICT (profile_id) DO UPDATE SET
    specialization = EXCLUDED.specialization,
    department_id  = EXCLUDED.department_id,
    service_area   = EXCLUDED.service_area,
    status         = 'ACTIVE',
    approved_by    = EXCLUDED.approved_by,
    approved_at    = EXCLUDED.approved_at,
    updated_at     = CURRENT_TIMESTAMP;


-- -----------------------------------------------------------------------------
-- 10. Verification output
-- -----------------------------------------------------------------------------
SELECT
    (SELECT count(*) FROM public.incidents
      WHERE id IN ('65449c49-8788-5782-8a90-669dbd09601e'::uuid,
                   '1e8d2a12-d20e-56b4-8f85-09706d01d98e'::uuid,
                   'f7ccbdc0-9863-57b7-a018-60885f702e76'::uuid,
                   'b4c4e204-e5e0-57e5-9955-24f3469195c4'::uuid,
                   '77aa6e3e-82e3-548a-8cbd-2d958f03fc90'::uuid)) AS demo_incidents,
    (SELECT count(*) FROM public.infrastructure_assets
      WHERE metadata ->> 'seed' = 'dhaka-demo') AS demo_assets,
    (SELECT count(*) FROM public.dependency_edges) AS dependency_edges,
    (SELECT count(*) FROM public.incident_relationships
      WHERE status = 'CONFIRMED') AS confirmed_relationships,
    (SELECT count(*) FROM public.worker_profiles
      WHERE status = 'ACTIVE') AS active_workers,
    (SELECT count(*) FROM public.decision_actions
      WHERE scenario_id = 'aea57bff-dcfa-5152-b952-b52e1e786edf'::uuid) AS scenario_actions,
    (SELECT count(*) FROM _cf_junk) AS junk_rows_removed;

COMMIT;

-- =============================================================================
-- 4-STEP DEMO RECORDING CHECKLIST
-- =============================================================================
-- 1. Citizen view  — sign in as the reporter profile, open /incidents and /map.
--                    Show the five clean Mirpur-10/Kazipara/Agargaon pins, then
--                    click a pin for the DOM-safe popup and address.
-- 2. Intelligence  — sign in as Admin, open an incident -> Intelligence tab.
--                    Show the confirmed cascade: blocked drain -> waterlogging
--                    -> hospital ambulance route, plus the canal and sinkhole
--                    context links. Open /risk: cluster at H3 res 8, click the
--                    hottest cell and show incident briefs + infrastructure
--                    exposure (hospital, trunk, arterial).
-- 3. Scenario      — open /decisions, select "Heavy Rainfall — Mirpur-10 to
--                    Agargaon Cascading Flood", press "Run simulation" and
--                    compare strategies on the scenario map. State clearly:
--                    planning simulation only, no dispatch or real orders.
-- 4. Workforce     — open /admin, show the 3 active approved workers with
--                    distinct zones/specializations, run candidate optimization
--                    on the critical incidents and assign one live. Then open
--                    /worker with that worker account to show the offered task.
-- =============================================================================
