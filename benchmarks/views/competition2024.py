from django.shortcuts import render

from .index import get_context


def view(request):
    # specify exact set of models used in this competition
    included_models = [
        # top-10 Brain-Score/vision models (as of 07.03.2024)
        'cvt_cvt-w24-384-in22k_finetuned-in1k_4',
        'resnext101_32x8d_wsl',
        'effnetb1_cutmixpatch_SAM_',
        'effnetb1_cutmixpatch_augmix_robust32_avge4e7_manylayers_324x288',  # winner competition 2022
        'resnext101_32x32d_wsl',
        'effnetb1_272x240',
        'resnext101_32x48d_wsl',
        'pnasnet_large',
        'resnet-152_v2',
        'focalnet_tiny_lrf_in1k',
        # 10 reference models
        'pixels',
        'hmax',
        # 'alexnet',
        'CORnet-S',
        # 'resnet-50-pytorch',
        'resnet-50-robust',
        'voneresnet-50-non_stochastic',
        # 'barlow-twins-resnet50',
        'resnet18-local_aggregation',
        'grcnn_robust_v1',  # top-3 competition 2022
        'custom_model_cv_18_dagger_408',  # top-3 competition 2022
        'ViT_L_32_imagenet1k',
        # 'efficientnet_b0',
        'mobilenet_v2_1.4_224',
        # 'deit_base_patch16_384_id',

    ]
    assert len(included_models) == 20
    # context = get_context(benchmark_filter=lambda benchmarks: benchmarks.filter(competition='2024'),
    #                       show_public=True)  # todo
    context = {}
    return render(request, 'benchmarks/competition2024.html', context)
