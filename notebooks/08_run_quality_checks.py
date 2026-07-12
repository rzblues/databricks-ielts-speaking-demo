# Databricks notebook source

"""Run non-mutating Delta quality checks and fail the job on violations."""

from datetime import datetime, timezone

checks = {
    "attempts_have_audio_paths": "SELECT COUNT(*) FROM main.ielts_demo.attempts WHERE audio_path IS NULL OR audio_path = ''",
    "segments_have_text": "SELECT COUNT(*) FROM main.ielts_demo.asr_segments WHERE text IS NULL OR trim(text) = ''",
    "features_in_valid_ranges": """
        SELECT COUNT(*) FROM main.ielts_demo.speech_features
        WHERE silence_ratio NOT BETWEEN 0 AND 1 OR lexical_diversity NOT BETWEEN 0 AND 1
           OR asr_confidence_proxy NOT BETWEEN 0 AND 1 OR words_per_min < 0
    """,
    "scores_in_valid_ranges": """
        SELECT COUNT(*) FROM main.ielts_demo.scoring_results
        WHERE overall_band NOT BETWEEN 0 AND 9 OR fc_band NOT BETWEEN 0 AND 9
           OR lr_band NOT BETWEEN 0 AND 9 OR gra_band NOT BETWEEN 0 AND 9 OR p_band NOT BETWEEN 0 AND 9
    """,
    "overall_matches_dimension_average": """
        SELECT COUNT(*) FROM main.ielts_demo.scoring_results
        WHERE overall_band <> round((fc_band + lr_band + gra_band + p_band) / 4.0 * 2) / 2
    """,
    "scoring_rows_have_provenance": """
        SELECT COUNT(*) FROM main.ielts_demo.scoring_results
        WHERE audio_source IS NULL OR asr_provider IS NULL OR asr_is_mock IS NULL
           OR scoring_provider IS NULL OR scoring_is_mock IS NULL OR pipeline_mode IS NULL
    """,
    "real_audio_rows_do_not_use_mock_asr": """
        SELECT COUNT(*) FROM main.ielts_demo.scoring_results
        WHERE pipeline_mode = 'real_audio' AND (audio_source <> 'real_audio' OR asr_is_mock = true)
    """,
    "scoring_rows_join_attempts": """
        SELECT COUNT(*) FROM main.ielts_demo.scoring_results sr
        LEFT JOIN main.ielts_demo.attempts a ON sr.attempt_id = a.attempt_id
        WHERE a.attempt_id IS NULL
    """,
}

check_time = datetime.now(timezone.utc)
results = []
for name, query in checks.items():
    failing_rows = int(spark.sql(query).first()[0])
    results.append(
        {
            "check_time": check_time,
            "check_name": name,
            "status": "PASS" if failing_rows == 0 else "FAIL",
            "failing_rows": failing_rows,
            "expectation_sql": " ".join(query.split()),
            "notes": "Databricks job non-mutating quality gate",
        }
    )

spark.createDataFrame(
    results, schema=spark.table("main.ielts_demo.quality_check_results").schema
).write.mode("append").saveAsTable("main.ielts_demo.quality_check_results")
failed = [result for result in results if result["status"] == "FAIL"]
if failed:
    raise RuntimeError(f"quality checks failed: {failed}")
print(f"quality checks passed count={len(results)}")
