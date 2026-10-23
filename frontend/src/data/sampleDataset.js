/**
 * Pre-bundled Realistic Multi-Cloud Sample Dataset
 * Enables zero-friction offline demo mode and immediate exploration.
 */

export const SAMPLE_ANALYSIS = {
  analysis_id: "anl_sample_prod_01",
  tenant_id: "tenant_demo",
  total_spend: 48250.40,
  expected_spend: 41800.00,
  dollars_at_risk: 6450.40,
  total_anomalies: 4,
  critical_anomalies_count: 1,
  high_anomalies_count: 2,
  top_moving_services: [
    { service: "AmazonEC2", actual: 24800.00, expected: 20100.00, delta: 4700.00, pct: 23.4 },
    { service: "AmazonRDS", actual: 11400.00, expected: 9900.00, delta: 1500.00, pct: 15.2 },
    { service: "AmazonS3", actual: 7850.40, expected: 7600.00, delta: 250.40, pct: 3.3 },
    { service: "GoogleCloudStorage", actual: 4200.00, expected: 4200.00, delta: 0.00, pct: 0.0 },
  ],
};

export const SAMPLE_ANOMALIES = [
  {
    anomaly_id: "anom_ec2_surge_01",
    analysis_id: "anl_sample_prod_01",
    service_name: "AmazonEC2",
    timestamp: "2026-03-14T03:00:00Z",
    actual_cost: 3840.00,
    expected_cost: 1120.00,
    deviation_cost: 2720.00,
    percentage_deviation: 242.8,
    severity: "Critical",
    top_cause: "USAGE_SPIKE",
    confidence_tier: "High",
    status: "New",
    user_feedback: null,
    narrative_markdown: `**Spend Deviation Briefing: AmazonEC2**

During the 1-hour window starting **2026-03-14 03:00 UTC**, AmazonEC2 incurred **$3,840.00**, representing an unexpected deviation of **+$2,720.00 (+242.8%)** above the forecast baseline of **$1,120.00**.

### Key Statistical Factors
- **Primary Driver:** The primary contributing factor is a sharp surge in compute instance volume (\`c5.9xlarge\` spot interruption failover to on-demand instances).
- **Attribution Evidence:** Volume change accounts for **84.2%** of the observed cost shift, while rate change represents **15.8%**.
- **Change Event Correlation:** An operational deployment (\`v2.4.1-worker-pool\`) was registered at **02:45 UTC**, 15 minutes prior to the spend jump.

### Recommended Action
1. Review the autoscaling group min/max instance thresholds for worker cluster \`prod-ml-inference\`.
2. Verify if spot instance fallback configurations can be restored to mitigate on-demand surcharge.`,
    evidence_refs: [
      "dim_subaccount_098234",
      "pvm_volume_effect_84pct",
      "event_deploy_v2_4_1"
    ],
    timeseries: [
      { time: "00:00", actual: 1100, expected: 1100 },
      { time: "01:00", actual: 1150, expected: 1120 },
      { time: "02:00", actual: 1110, expected: 1115 },
      { time: "03:00", actual: 3840, expected: 1120, isAnomaly: true },
      { time: "04:00", actual: 2900, expected: 1130, isAnomaly: true },
      { time: "05:00", actual: 1800, expected: 1140 },
      { time: "06:00", actual: 1200, expected: 1125 },
    ],
    shap_contributions: [
      { feature: "usage_quantity_surge", value: "+$1,940.00", pct: 71.3 },
      { feature: "on_demand_rate_mix", value: "+$520.00", pct: 19.1 },
      { feature: "cross_az_traffic", value: "+$260.00", pct: 9.6 },
    ],
  },
  {
    anomaly_id: "anom_rds_storage_02",
    analysis_id: "anl_sample_prod_01",
    service_name: "AmazonRDS",
    timestamp: "2026-03-14T11:00:00Z",
    actual_cost: 1850.00,
    expected_cost: 720.00,
    deviation_cost: 1130.00,
    percentage_deviation: 156.9,
    severity: "High",
    top_cause: "VOLUME_SURGE",
    confidence_tier: "High",
    status: "Investigating",
    user_feedback: "USEFUL",
    narrative_markdown: `**Spend Deviation Briefing: AmazonRDS**

During **2026-03-14 11:00 UTC**, AmazonRDS registered **$1,850.00**, exceeding the baseline projection of **$720.00** by **+$1,130.00 (+156.9%)**.

### Key Statistical Factors
- **Primary Driver:** Provisioned IOPS auto-scaling coinciding with a batch analytical ingestion query on the replica database cluster.
- **Attribution Evidence:** Rate changes were 0%, pure storage allocation and IOPS provisioning accounted for **100%** of the delta.

### Recommended Action
Confirm if read-heavy batch jobs can be scheduled during off-peak discount windows.`,
    evidence_refs: [
      "dim_subaccount_database_prod",
      "pvm_volume_effect_100pct"
    ],
    timeseries: [
      { time: "08:00", actual: 710, expected: 720 },
      { time: "09:00", actual: 730, expected: 715 },
      { time: "10:00", actual: 750, expected: 725 },
      { time: "11:00", actual: 1850, expected: 720, isAnomaly: true },
      { time: "12:00", actual: 1400, expected: 730 },
      { time: "13:00", actual: 780, expected: 720 },
    ],
    shap_contributions: [
      { feature: "iops_provisioned_delta", value: "+$890.00", pct: 78.8 },
      { feature: "storage_gb_hours", value: "+$240.00", pct: 21.2 },
    ],
  },
  {
    anomaly_id: "anom_ec2_network_03",
    analysis_id: "anl_sample_prod_01",
    service_name: "AmazonEC2",
    timestamp: "2026-03-15T18:00:00Z",
    actual_cost: 920.00,
    expected_cost: 410.00,
    deviation_cost: 510.00,
    percentage_deviation: 124.4,
    severity: "High",
    top_cause: "PRICE_RATE_CHANGE",
    confidence_tier: "Medium",
    status: "New",
    user_feedback: null,
    narrative_markdown: `**Spend Deviation Briefing: AmazonEC2 Data Transfer**

During **2026-03-15 18:00 UTC**, data transfer egress between us-east-1 and eu-central-1 experienced a temporary surge of **+$510.00 (+124.4%)**.`,
    evidence_refs: ["dim_region_inter_az"],
    timeseries: [
      { time: "15:00", actual: 410, expected: 410 },
      { time: "16:00", actual: 420, expected: 410 },
      { time: "17:00", actual: 450, expected: 415 },
      { time: "18:00", actual: 920, expected: 410, isAnomaly: true },
      { time: "19:00", actual: 510, expected: 410 },
    ],
    shap_contributions: [
      { feature: "inter_region_egress_bytes", value: "+$410.00", pct: 80.4 },
      { feature: "nat_gateway_processing", value: "+$100.00", pct: 19.6 },
    ],
  },
  {
    anomaly_id: "anom_s3_requests_04",
    analysis_id: "anl_sample_prod_01",
    service_name: "AmazonS3",
    timestamp: "2026-03-16T08:00:00Z",
    actual_cost: 320.00,
    expected_cost: 160.00,
    deviation_cost: 160.00,
    percentage_deviation: 100.0,
    severity: "Medium",
    top_cause: "USAGE_SPIKE",
    confidence_tier: "Low",
    status: "Resolved",
    user_feedback: "PLANNED",
    narrative_markdown: `**Spend Deviation Briefing: AmazonS3 API Requests**

During **2026-03-16 08:00 UTC**, PUT/LIST API requests jumped by **+$160.00 (+100.0%)**. Marked as planned maintenance crawler run.`,
    evidence_refs: ["dim_bucket_audit_logs"],
    timeseries: [
      { time: "06:00", actual: 160, expected: 160 },
      { time: "07:00", actual: 165, expected: 160 },
      { time: "08:00", actual: 320, expected: 160, isAnomaly: true },
      { time: "09:00", actual: 180, expected: 160 },
    ],
    shap_contributions: [
      { feature: "list_bucket_request_count", value: "+$120.00", pct: 75.0 },
      { feature: "put_object_request_count", value: "+$40.00", pct: 25.0 },
    ],
  },
];
