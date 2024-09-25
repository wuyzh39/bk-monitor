from typing import Any, Dict, List

from apm_web.profile.resources import ListApplicationServicesResource
from apm_web.trace.resources import (
    GetFieldOptionValuesResource,
    ListStandardFilterFieldsResource,
    ListTraceResource,
    TraceDetailResource,
)


class GetTraceApplicationResource(ListApplicationServicesResource):
    pass


class GetTraceFields(ListStandardFilterFieldsResource):
    def perform_request(self, validate_data):
        """
        展开嵌套的children，将所有Tag打平到第一层
        """
        res = super().perform_request(validate_data)
        res_without_children = []
        for item in res:
            res_without_children += self.get_base_attributes(item)
        return res_without_children

    def get_base_attributes(self, data: Dict) -> List:
        if data.get("children"):
            res = []
            for item in data["children"]:
                res.append(self.get_base_attributes(item))
            return res
        else:
            return [data]


class GetFieldValuesResource(GetFieldOptionValuesResource):
    pass


class QueryTraceResource(ListTraceResource):
    pass


class ShowTraceDetailResource(TraceDetailResource):
    def perform_request(self, validated_request_data):
        data = super().perform_request(validated_request_data)
        # 构造符合grafana格式的返回值
        trace_id = self.transform_to_list_by_field(data["trace_tree"]["spans"], ["traceID"])
        span_id = self.transform_to_list_by_field(data["trace_tree"]["spans"], ["id"])
        parent_span_id = self.transform_to_list_by_field(data["original_data"], ["parent_span_id"])
        operation_name = self.transform_to_list_by_field(data["original_data"], ["span_name"])
        service_name = self.transform_to_list_by_field(data["trace_tree"]["spans"], ["service_name"])
        service_tags = self.transform_to_list_by_field(data["original_data"], ["resource"])
        service_tags = self.transform_dict_to_kv_lists(service_tags)
        start_time = self.transform_to_list_by_field(data["original_data"], ["start_time"])
        start_time = [t / 1000 for t in start_time]
        duration = self.transform_to_list_by_field(data["original_data"], ["elapsed_time"])
        duration = [t / 1000 for t in duration]
        kind = self.transform_to_list_by_field(data["original_data"], ["kind"])
        status_code = self.transform_to_list_by_field(data["original_data"], ["status", "code"])
        tags = self.transform_to_list_by_field(data["original_data"], ["attributes"])
        tags = self.transform_dict_to_kv_lists(tags)
        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "operation_name": operation_name,
            "service_name": service_name,
            "service_tags": service_tags,
            "start_time": start_time,
            "duration": duration,
            "kind": kind,
            "status_code": status_code,
            "tags": tags,
        }

    def transform_to_list_by_field(self, data: List[Dict[str, Any]], fields: List[str]) -> List[Any]:
        """
        将list[dict]中的某字段抽出来成一个list
        """
        if len(data) <= 0:
            return []

        field_list = data
        for field in fields:
            field_list = [item.get(field, "") if isinstance(item, dict) else "" for item in field_list]

        return field_list

    def transform_dict_to_kv_lists(self, input_dict_list):
        """
        将列表中的每个形如{"k1": "v1", "k2": "v2"}的dict转为[{"key": "k1", "value": "v1"}, {"key": "k2", "value": "v2"}]
        """
        result = []
        for single_dict in input_dict_list:
            result.append([{"key": k, "value": v} for k, v in single_dict.items()])
        return result
