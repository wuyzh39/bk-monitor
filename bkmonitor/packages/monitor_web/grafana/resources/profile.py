import itertools
import json

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK

from apm_web.profile.constants import (
    DEFAULT_PROFILE_DATA_TYPE,
    DEFAULT_SERVICE_NAME,
    LARGE_SERVICE_MAX_QUERY_SIZE,
    NORMAL_SERVICE_MAX_QUERY_SIZE,
    CallGraphResponseDataMode,
)
from apm_web.profile.diagrams import get_diagrammer
from apm_web.profile.doris.querier import APIType, ConverterType
from apm_web.profile.resources import (
    ListApplicationServicesResource,
    QueryServicesDetailResource,
)
from apm_web.profile.serializers import QueryBaseSerializer
from apm_web.profile.views import ProfileQueryViewSet
from core.drf_resource import Resource


class QueryGraphProfileResource(Resource):
    class RequestSerializer(serializers.Serializer):
        profile_id = serializers.CharField(label="profile ID", required=False, default="")
        offset = serializers.IntegerField(label="偏移量(秒)", required=False, default=0)
        filter_labels = serializers.DictField(label="标签过滤", default={}, required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称", required=False)
        service_name = serializers.CharField(label="服务名称", required=False)
        data_type = serializers.CharField(
            label="采样类型(sample_type,前端显示为 data_type )",
            required=False,
            default=DEFAULT_PROFILE_DATA_TYPE,
        )
        start = serializers.IntegerField(label="开始时间", help_text="请使用 Microsecond", required=False)
        start_time = serializers.IntegerField(label="开始时间", help_text="请使用 Second", required=False)
        end = serializers.IntegerField(label="结束时间", help_text="请使用 Microsecond", required=False)
        end_time = serializers.IntegerField(label="结束时间", help_text="请使用 Second", required=False)

    def perform_request(self, params):
        start, end = int(params["start"] / 1000), int(params["end"] / 1000)
        essentials = get_essentials(params)
        # 根据是否是大应用调整获取的消息条数 避免接口耗时过长
        if ProfileQueryViewSet().is_large_service(
            essentials["bk_biz_id"],
            essentials["app_name"],
            essentials["service_name"],
            params["data_type"],
        ):
            extra_params = {"limit": {"offset": 0, "rows": LARGE_SERVICE_MAX_QUERY_SIZE}}
        else:
            extra_params = {"limit": {"offset": 0, "rows": NORMAL_SERVICE_MAX_QUERY_SIZE}}
        tree_converter = ProfileQueryViewSet.query(
            bk_biz_id=essentials["bk_biz_id"],
            app_name=essentials["app_name"],
            service_name=essentials["service_name"],
            start=start,
            end=end,
            profile_id=params.get("profile_id"),
            filter_labels=params.get("filter_labels"),
            result_table_id=essentials["result_table_id"],
            sample_type=params["data_type"],
            converter=ConverterType.Tree,
            extra_params=extra_params,
        )

        if not tree_converter or tree_converter.empty():
            return Response(_("未查询到有效数据"), status=HTTP_200_OK)

        options = {"sort": params.get("sort"), "data_mode": CallGraphResponseDataMode.IMAGE_DATA_MODE}
        flame_data = get_diagrammer("grafana_flame").draw(tree_converter, **options)

        return Response(data=flame_data)


class GetProfileApplicationServiceResource(ListApplicationServicesResource):
    pass


class GetProfileTypeResource(QueryServicesDetailResource):
    pass


class GetProfileLabelResource(Resource):
    class RequestSerializer(QueryBaseSerializer):
        pass

    def perform_request(self, data):
        limit = 1000

        essentials = get_essentials(data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = ProfileQueryViewSet()._enlarge_duration(data["start"], data["end"], offset=300)

        # 因为 bkbase label 接口已经改为返回原始格式的所以这里改成取前 5000条 label 进行提取 key 列表
        results = ProfileQueryViewSet.query(
            api_type=APIType.LABELS,
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            result_table_id=result_table_id,
            start=start,
            end=end,
            extra_params={"limit": {"rows": limit}},
        )

        label_keys = set(
            itertools.chain(*[list(json.loads(i["labels"]).keys()) for i in results.get("list", {}) if i.get("labels")])
        )

        return {"label_keys": label_keys}


class GetProfileLabelValuesResource(Resource):
    class RequestSerializer(QueryBaseSerializer):
        label_key = serializers.CharField(label="label名")
        offset = serializers.IntegerField(label="label_values查询起点")
        rows = serializers.IntegerField(label="label_values查询条数")

    def perform_request(self, data):
        """获取 profiling 数据的 label_values 列表"""

        offset, rows = data["offset"], data["rows"]
        essentials = get_essentials(data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = ProfileQueryViewSet._enlarge_duration(data["start"], data["end"], offset=300)
        results = ProfileQueryViewSet.query(
            api_type=APIType.LABEL_VALUES,
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            extra_params={
                "label_key": data["label_key"],
                "limit": {"offset": offset, "rows": rows},
            },
            result_table_id=result_table_id,
            start=start,
            end=end,
        )

        return Response(
            data={"label_values": [i["label_value"] for i in results.get("list", {}) if i.get("label_value")]}
        )


def get_essentials(data):
    bk_biz_id = data["bk_biz_id"]
    app_name = data["app_name"]
    service_name = data.get("service_name", DEFAULT_SERVICE_NAME)
    application_info = ProfileQueryViewSet()._examine_application(bk_biz_id, app_name)
    result_table_id = application_info["profiling_config"]["result_table_id"]

    return {
        "bk_biz_id": bk_biz_id,
        "app_name": app_name,
        "service_name": service_name,
        "result_table_id": result_table_id,
    }
