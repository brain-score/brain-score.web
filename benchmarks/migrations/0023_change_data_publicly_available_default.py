"""
Change data_publicly_available default from True to False.

Data is considered private unless explicitly marked public.
This migration:
1. Changes the field default to False
2. Sets all existing rows to False (previous default of True was incorrect)
3. Marks benchmarks with verified public S3 data as True

Verified via scripts/validate_public_access.py which checks anonymous HEAD
requests against each S3 object referenced by benchmark data plugins.
"""

from django.db import migrations, models

# 160 auto-detected (all data in plugin is public) + 7 manual (public variants
# in mixed public/private plugins: freemanziemba2013, majajhong2015, rajalingham2018)
PUBLIC_BENCHMARK_IDENTIFIERS = [
    # baker2022 (3)
    'Baker2022fragmented-accuracy_delta',
    'Baker2022frankenstein-accuracy_delta',
    'Baker2022inverted-accuracy_delta',
    # bmd2024 (4)
    'BMD2024.dotted_1Behavioral-accuracy_distance',
    'BMD2024.dotted_2Behavioral-accuracy_distance',
    'BMD2024.texture_1Behavioral-accuracy_distance',
    'BMD2024.texture_2Behavioral-accuracy_distance',
    # bracci2019 (3)
    'Bracci2019.anteriorVTC-rdm',
    'Bracci2019_RSA-V1',
    'Bracci2019_RSA-posteriorVTC',
    # cadena2017 (2)
    'Cadena2017-mask',
    'Cadena2017-pls',
    # coggan2024_behavior (1)
    'tong.Coggan2024_behavior-ConditionWiseAccuracySimilarity',
    # coggan2024_fMRI (4)
    'tong.Coggan2024_fMRI.IT-rdm',
    'tong.Coggan2024_fMRI.V1-rdm',
    'tong.Coggan2024_fMRI.V2-rdm',
    'tong.Coggan2024_fMRI.V4-rdm',
    # ferguson2024 (14)
    'Ferguson2024circle_line-value_delta',
    'Ferguson2024color-value_delta',
    'Ferguson2024convergence-value_delta',
    'Ferguson2024eighth-value_delta',
    'Ferguson2024gray_easy-value_delta',
    'Ferguson2024gray_hard-value_delta',
    'Ferguson2024half-value_delta',
    'Ferguson2024juncture-value_delta',
    'Ferguson2024lle-value_delta',
    'Ferguson2024llh-value_delta',
    'Ferguson2024quarter-value_delta',
    'Ferguson2024round_f-value_delta',
    'Ferguson2024round_v-value_delta',
    'Ferguson2024tilted_line-value_delta',
    # freemanziemba2013 public variants (2) -- manual
    'FreemanZiemba2013public.V1-pls',
    'FreemanZiemba2013public.V2-pls',
    # geirhos2021 (34)
    'Geirhos2021colour-error_consistency',
    'Geirhos2021colour-top1',
    'Geirhos2021contrast-error_consistency',
    'Geirhos2021contrast-top1',
    'Geirhos2021cueconflict-error_consistency',
    'Geirhos2021cueconflict-top1',
    'Geirhos2021edge-error_consistency',
    'Geirhos2021edge-top1',
    'Geirhos2021eidolonI-error_consistency',
    'Geirhos2021eidolonI-top1',
    'Geirhos2021eidolonII-error_consistency',
    'Geirhos2021eidolonII-top1',
    'Geirhos2021eidolonIII-error_consistency',
    'Geirhos2021eidolonIII-top1',
    'Geirhos2021falsecolour-error_consistency',
    'Geirhos2021falsecolour-top1',
    'Geirhos2021highpass-error_consistency',
    'Geirhos2021highpass-top1',
    'Geirhos2021lowpass-error_consistency',
    'Geirhos2021lowpass-top1',
    'Geirhos2021phasescrambling-error_consistency',
    'Geirhos2021phasescrambling-top1',
    'Geirhos2021powerequalisation-error_consistency',
    'Geirhos2021powerequalisation-top1',
    'Geirhos2021rotation-error_consistency',
    'Geirhos2021rotation-top1',
    'Geirhos2021silhouette-error_consistency',
    'Geirhos2021silhouette-top1',
    'Geirhos2021sketch-error_consistency',
    'Geirhos2021sketch-top1',
    'Geirhos2021stylized-error_consistency',
    'Geirhos2021stylized-top1',
    'Geirhos2021uniformnoise-error_consistency',
    'Geirhos2021uniformnoise-top1',
    # hebart2023 (1)
    'Hebart2023-match',
    # hermann2020 (2)
    'Hermann2020cueconflict-shape_bias',
    'Hermann2020cueconflict-shape_match',
    # igustibagus2024 (2)
    'Igustibagus2024-ridge',
    'Igustibagus2024.IT_readout-accuracy',
    # islam2021 (8)
    'Islam2021-shape_it_dimensionality',
    'Islam2021-shape_v1_dimensionality',
    'Islam2021-shape_v2_dimensionality',
    'Islam2021-shape_v4_dimensionality',
    'Islam2021-texture_it_dimensionality',
    'Islam2021-texture_v1_dimensionality',
    'Islam2021-texture_v2_dimensionality',
    'Islam2021-texture_v4_dimensionality',
    # lonnqvist2024 (4)
    'Lonnqvist2024_EngineeringAccuracy',
    'Lonnqvist2024_InlabInstructionsBehavioralAccuracyDistance',
    'Lonnqvist2024_InlabNoInstructionsBehavioralAccuracyDistance',
    'Lonnqvist2024_OnlineNoInstructionsBehavioralAccuracyDistance',
    # majajhong2015 public variants (4) -- manual
    'MajajHong2015public.IT-pls',
    'MajajHong2015public.IT-temporal-pls',
    'MajajHong2015public.V4-pls',
    'MajajHong2015public.V4-temporal-pls',
    # malania2007 (10)
    'Malania2007.equal16-threshold_elevation',
    'Malania2007.equal2-threshold_elevation',
    'Malania2007.long16-threshold_elevation',
    'Malania2007.long2-threshold_elevation',
    'Malania2007.short16-threshold_elevation',
    'Malania2007.short2-threshold_elevation',
    'Malania2007.short4-threshold_elevation',
    'Malania2007.short6-threshold_elevation',
    'Malania2007.short8-threshold_elevation',
    'Malania2007.vernieracuity-threshold',
    # maniquet2024 (2)
    'Maniquet2024-confusion_similarity',
    'Maniquet2024-tasks_consistency',
    # marques2020 (22)
    'Marques2020_Cavanaugh2002-grating_summation_field',
    'Marques2020_Cavanaugh2002-surround_diameter',
    'Marques2020_Cavanaugh2002-surround_suppression_index',
    'Marques2020_DeValois1982-peak_sf',
    'Marques2020_DeValois1982-pref_or',
    'Marques2020_FreemanZiemba2013-abs_texture_modulation_index',
    'Marques2020_FreemanZiemba2013-max_noise',
    'Marques2020_FreemanZiemba2013-max_texture',
    'Marques2020_FreemanZiemba2013-texture_modulation_index',
    'Marques2020_FreemanZiemba2013-texture_selectivity',
    'Marques2020_FreemanZiemba2013-texture_sparseness',
    'Marques2020_FreemanZiemba2013-texture_variance_ratio',
    'Marques2020_Ringach2002-circular_variance',
    'Marques2020_Ringach2002-cv_bandwidth_ratio',
    'Marques2020_Ringach2002-max_dc',
    'Marques2020_Ringach2002-modulation_ratio',
    'Marques2020_Ringach2002-opr_cv_diff',
    'Marques2020_Ringach2002-or_bandwidth',
    'Marques2020_Ringach2002-or_selective',
    'Marques2020_Ringach2002-orth_pref_ratio',
    'Marques2020_Schiller1976-sf_bandwidth',
    'Marques2020_Schiller1976-sf_selective',
    # rajalingham2018 public variant (1) -- manual
    'Rajalingham2018public-i2n',
    # scialom2024 (44)
    'Scialom2024_contoursBehavioralAccuracyDistance',
    'Scialom2024_contoursEngineeringAccuracy',
    'Scialom2024_phosphenes-100BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-100EngineeringAccuracy',
    'Scialom2024_phosphenes-12BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-12EngineeringAccuracy',
    'Scialom2024_phosphenes-16BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-16EngineeringAccuracy',
    'Scialom2024_phosphenes-21BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-21EngineeringAccuracy',
    'Scialom2024_phosphenes-27BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-27EngineeringAccuracy',
    'Scialom2024_phosphenes-35BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-35EngineeringAccuracy',
    'Scialom2024_phosphenes-46BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-46EngineeringAccuracy',
    'Scialom2024_phosphenes-59BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-59EngineeringAccuracy',
    'Scialom2024_phosphenes-77BehavioralAccuracyDistance',
    'Scialom2024_phosphenes-77EngineeringAccuracy',
    'Scialom2024_phosphenes-allBehavioralAccuracyDistance',
    'Scialom2024_phosphenes-allBehavioralErrorConsistency',
    'Scialom2024_rgbBehavioralAccuracyDistance',
    'Scialom2024_rgbEngineeringAccuracy',
    'Scialom2024_segments-100BehavioralAccuracyDistance',
    'Scialom2024_segments-100EngineeringAccuracy',
    'Scialom2024_segments-12BehavioralAccuracyDistance',
    'Scialom2024_segments-12EngineeringAccuracy',
    'Scialom2024_segments-16BehavioralAccuracyDistance',
    'Scialom2024_segments-16EngineeringAccuracy',
    'Scialom2024_segments-21BehavioralAccuracyDistance',
    'Scialom2024_segments-21EngineeringAccuracy',
    'Scialom2024_segments-27BehavioralAccuracyDistance',
    'Scialom2024_segments-27EngineeringAccuracy',
    'Scialom2024_segments-35BehavioralAccuracyDistance',
    'Scialom2024_segments-35EngineeringAccuracy',
    'Scialom2024_segments-46BehavioralAccuracyDistance',
    'Scialom2024_segments-46EngineeringAccuracy',
    'Scialom2024_segments-59BehavioralAccuracyDistance',
    'Scialom2024_segments-59EngineeringAccuracy',
    'Scialom2024_segments-77BehavioralAccuracyDistance',
    'Scialom2024_segments-77EngineeringAccuracy',
    'Scialom2024_segments-allBehavioralAccuracyDistance',
    'Scialom2024_segments-allBehavioralErrorConsistency',
]


def mark_public_benchmarks(apps, schema_editor):
    BenchmarkInstance = apps.get_model('benchmarks', 'BenchmarkInstance')
    BenchmarkDataMeta = apps.get_model('benchmarks', 'BenchmarkDataMeta')

    meta_ids = set(
        BenchmarkInstance.objects
        .filter(benchmark_identifier__in=PUBLIC_BENCHMARK_IDENTIFIERS)
        .exclude(data_meta_id__isnull=True)
        .values_list('data_meta_id', flat=True)
    )
    if meta_ids:
        BenchmarkDataMeta.objects.filter(id__in=meta_ids).update(data_publicly_available=True)


def unmark_public_benchmarks(apps, schema_editor):
    BenchmarkDataMeta = apps.get_model('benchmarks', 'BenchmarkDataMeta')
    BenchmarkDataMeta.objects.all().update(data_publicly_available=True)


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0022_model_group'),
    ]

    operations = [
        # Step 1: Change field default
        migrations.AlterField(
            model_name='benchmarkdatameta',
            name='data_publicly_available',
            field=models.BooleanField(default=False),
        ),
        # Step 2: Reset all to False
        migrations.RunSQL(
            sql="UPDATE brainscore_benchmark_data_meta SET data_publicly_available = FALSE;",
            reverse_sql="UPDATE brainscore_benchmark_data_meta SET data_publicly_available = TRUE;",
        ),
        # Step 3: Mark verified-public benchmarks as True
        migrations.RunPython(mark_public_benchmarks, unmark_public_benchmarks),
    ]
