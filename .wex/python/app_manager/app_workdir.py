from __future__ import annotations

from typing import TYPE_CHECKING

from wexample_wex_addon_dev_python.workdir.python_package_workdir import PythonPackageWorkdir

if TYPE_CHECKING:
    from wexample_config.const.types import DictConfig


class AppWorkdir(PythonPackageWorkdir):
    def prepare_value(self, raw_value: DictConfig | None = None) -> DictConfig:
        from wexample_helpers.helpers.string import string_to_kebab_case

        raw_value = super().prepare_value(raw_value=raw_value)

        def _build_remote_github(target: AppWorkdir) -> str:
            return f"git@github.com:wexample/python-{string_to_kebab_case(target.get_project_name())}.git"

        def _build_remote_gitlab(target: AppWorkdir) -> str:
            return f"ssh://git@gitlab.wexample.com:4567/wexample-python/{string_to_kebab_case(target.get_project_name())}.git"

        raw_value["git"] = {
            "main_branch": "main",
            "remote": [
                {
                    "name": "origin",
                    "type": "gitlab",
                    "url": _build_remote_gitlab,
                    "create_remote": True,
                },
                {
                    "name": "github",
                    "type": "github",
                    "url": _build_remote_github,
                    "create_remote": True,
                },
            ]
        }

        return raw_value
