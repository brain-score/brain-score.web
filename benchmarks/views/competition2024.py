from django.shortcuts import render

from .index import get_context
from ..models import User


def view(request):
    # model filter
    included_models = [
        "cvt_cvt-w24-384-in22k_finetuned-in1k_4",
        "resnext101_32x8d_wsl",
        "effnetb1_cutmixpatch_SAM_robust32_avge6e8e9e10_manylayers_324x288",
        "effnetb1_cutmixpatch_augmix_robust32_avge4e7_manylayers_324x288",
        "resnext101_32x32d_wsl",
        "effnetb1_272x240",
        "resnext101_32x48d_wsl",
        "pnasnet_large_pytorch",
        "resnet-152_v2_pytorch",
        "focalnet_tiny_lrf_in1k",
        "hmax",
        "alexnet",
        "CORnet-S",
        "resnet-50-robust",
        "voneresnet-50-non_stochastic",
        # "resnet18-local_aggregation",  # TF no longer supported
        # "grcnn_robust_v1",  # weights deleted on user server
        "custom_model_cv_18_dagger_408",
        "ViT_L_32_imagenet1k",
        "mobilenet_v2_1-4_224_pytorch",
        "pixels",
    ]
    assert len(included_models) == 19
    model_filter = dict(model__name__in=included_models)

    # benchmark filter
    track_benchmarks = {
        "behavior_vision": [
            "average_vision",
            "behavior_vision",

            "Hebart2023-match",

            "Baker2022",
            "Baker2022inverted-accuracy_delta", "Baker2022fragmented-accuracy_delta",
            "Baker2022frankenstein-accuracy_delta",

            "tong.Coggan2024_behavior-ConditionWiseAccuracySimilarity",

            "BMD2024",
            "BMD2024.texture_1Behavioral-accuracy_distance",
            "BMD2024.texture_2Behavioral-accuracy_distance",
            "BMD2024.dotted_1Behavioral-accuracy_distance",
            "BMD2024.dotted_2Behavioral-accuracy_distance",

            "Maniquet2024",
            "Maniquet2024-confusion_similarity", "Maniquet2024-tasks_consistency",

            # "Malania2007",
            # "Malania2007.short2", "Malania2007.short4", "Malania2007.short6", "Malania2007.short8",
            # "Malania2007.short16", "Malania2007.equal2", "Malania2007.long2", "Malania2007.equal16",
            # "Malania2007.long16", "Malania2007.vernieracuity-threshold",
            #
            # "Scialom2024",
            # "Scialom2024_rgb-behavioral_accuracy",
            # "Scialom2024_phosphenes-all-behavioral_accuracy",
            # "Scialom2024_segments-all-behavioral_accuracy",
            # "Scialom2024_phosphenes-100-behavioral_accuracy",
            # "Scialom2024_segments-100-behavioral_accuracy",
            #
            # "Ferguson2024",
            # "Ferguson2024circle_line-value_delta", "Ferguson2024color-value_delta",
            # "Ferguson2024convergence-value_delta", "Ferguson2024eighth-value_delta",
            # "Ferguson2024gray_easy-value_delta", "Ferguson2024gray_hard-value_delta", "Ferguson2024half-value_delta",
            # "Ferguson2024juncture-value_delta", "Ferguson2024lle-value_delta", "Ferguson2024llh-value_delta",
            # "Ferguson2024quarter-value_delta", "Ferguson2024round_f-value_delta", "Ferguson2024round_v-value_delta",
            # "Ferguson2024tilted_line-value_delta"
        ],
        "neural_vision": [
            "average_vision",
            "neural_vision",
            "V1", "V2", "V4", "IT",
            "Bracci2019.anteriorVTC-rdm",
            "Coggan2024",
            "tong.Coggan2024_fMRI.V1-rdm",
            "tong.Coggan2024_fMRI.V2-rdm",
            "tong.Coggan2024_fMRI.V4-rdm",
            "tong.Coggan2024_fMRI.IT-rdm",
        ]
    }
    admin_user = User.objects.get(id=2)
    context = {'leaderboard_keys': ['behavior_vision', 'neural_vision']}
    for key, key_benchmarks in track_benchmarks.items():
        benchmark_filter = lambda benchmarks: benchmarks.filter(identifier__in=key_benchmarks)
        key_context = get_context(benchmark_filter=benchmark_filter,
                                  model_filter=model_filter,
                                  user=admin_user,
                                  domain="vision", show_public=True)
        key_context[f"benchmarks_{key}"] = key_context['benchmarks']
        key_context[f"models_{key}"] = key_context['models']
        del key_context['benchmarks'], key_context['models']
        context = {**context, **key_context}

    return render(request, 'benchmarks/competition2024.html', context)
