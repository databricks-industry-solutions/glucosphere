-- Silver: Patient Registry
CREATE OR REFRESH MATERIALIZED VIEW silver_patient_registry
COMMENT 'Reference registry of patient-device-region-diagnosis relationships. Ensures join-ability and consistency for segment analysis across gold layers.'
AS SELECT
  patient_id,
  device_id,
  region,
  diagnosis AS patient_diagnosis,
  activation_date,
  birth_year,
  device_model
FROM read_files(
  '/Volumes/${catalog}/${schema}/pipeline_data/raw_patient_registry/',
  format => 'parquet'
);


-- Silver: Device Telemetry Stream
CREATE OR REFRESH MATERIALIZED VIEW silver_device_telemetry_stream
COMMENT 'Cleaned streaming device telemetry includes device firmware_version. Used for time-series event analysis and device activity rollup.'
AS SELECT
  patient_id,
  device_id,
  device_model,
  start_time,
  end_time,
  firmware_version
FROM read_files(
  '/Volumes/${catalog}/${schema}/pipeline_data/raw_device_telemetry_stream/',
  format => 'parquet'
);


-- Silver: Patient Readings
CREATE OR REFRESH MATERIALIZED VIEW silver_patient_readings
COMMENT 'patient glucose and biometric readings.'
AS SELECT
  patient_id,
  time,
  case when glucose_observed < 70 then 'hypoglycemia' when glucose_observed > 180 then 'hyperglycemia' else 'in_range' end as event_type,
  case when glucose_observed < 70 then 1 when glucose_observed > 180 then 1 when incident_type is null then 0 else 1 end as glucose_out_of_range,
  greatest(least(glucose_observed, 400), 40) as glucose,  -- CGM ceiling/floor (HI>400, LO<40); gold-layer backstop so device-observed glucose is always physiological regardless of source
  steps,
  basal_rate,
  bolus_volume_delivered,
  carb_input,
  heart_rate,
  calories,
  basal_present,
  bolus_event,
  carb_event
FROM ${catalog}.${schema}.pseudo_incident_7d_labeled;



-- Gold: Patient CGM Readings
CREATE OR REFRESH MATERIALIZED VIEW gold_patient_device_readings
COMMENT 'patient glucose and biometric readings with device and firmware version.'
AS SELECT
  a.patient_id,
  a.time,
  b.region,
  b.patient_diagnosis,
  b.activation_date,
  b.birth_year,
  c.device_id,
  b.device_model,  -- registry SSOT: device_model is a fixed per-device property, so take it from the registry (one row/patient), NOT the time-fuzzy telemetry temporal join (which disagreed for ~82% of readings). firmware_version below stays from telemetry (it IS time-varying).
  c.firmware_version,
  a.glucose,
  a.glucose_out_of_range,
  a.event_type,
  a.steps,
  a.basal_rate,
  a.bolus_volume_delivered,
  a.carb_input,
  a.heart_rate,
  a.calories,
  a.basal_present,
  a.bolus_event,
  a.carb_event

FROM silver_patient_readings a

left outer join silver_patient_registry b
on a.patient_id = b.patient_id

left outer join silver_device_telemetry_stream c
on a.patient_id = c.patient_id
and a.time between c.start_time and c.end_time
