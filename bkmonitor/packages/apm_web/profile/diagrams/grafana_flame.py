"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from dataclasses import dataclass

from apm_web.profile.diagrams.base import FunctionNode
from apm_web.profile.diagrams.tree_converter import TreeConverter


@dataclass
class GrafanaFlameDiagrammer:
    def draw(self, c: TreeConverter, **_) -> dict:
        levels = []
        labels = []
        values = []
        selfs = []
        root = c.tree.root
        self.preorder(root, 0, levels, labels, values, selfs)
        data = {"grafanaFlame": {"levels": levels, "labels": labels, "values": values, "selfs": selfs}}

        return data

    def preorder(self, root: FunctionNode, level: int, levels, labels, values, selfs) -> None:
        levels.append(level)
        labels.append(root.id)
        values.append(root.value)
        selfs.append(root.self_time)

        for child in root.children:
            self.preorder(child, level + 1, levels, labels, values, selfs)
