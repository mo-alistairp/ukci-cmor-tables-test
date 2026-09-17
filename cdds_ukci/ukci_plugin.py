# (C) British Crown Copyright 2023-2024, Met Office.
# Please see LICENSE.rst for license details.
"""
A Sample module for Adding a new project to CDDS, updated for CDDS v3.0.0.

This will require MIP tables and CVs and an appropriate request JSON file.

Note that this module must be installed somehow, e.g. through inclusion in
a .pth file in your local python site-packages directory
($HOME/.local/python3.8/site-packages/cdds.pth)
"""

import logging
import os
from typing import Type

from cdds.common.plugins.base.base_models import BaseModelParameters, BaseModelStore, ModelId
from cdds.common.plugins.base.base_plugin import BasePlugin
from cdds.common.plugins.base.base_streams import BaseStreamInfo, BaseStreamStore
from cdds.common.plugins.cmip6.cmip6_attributes import Cmip6GlobalAttributes
from cdds.common.plugins.cmip6.cmip6_grid import Cmip6GridLabel
from cdds.common.plugins.common import LoadResults
from cdds.common.plugins.file_info import GlobalModelFileInfo, ModelFileInfo
from cdds.common.plugins.grid import GridLabel
from cdds.common.plugins.models import ModelParameters
from cdds.common.plugins.streams import StreamInfo

UKCI_LICENSE = (
    "UKCI data produced by MOHC is licensed under the Open Government License v3 "
    "(https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)"
)


class UKCIModelId(ModelId):
    """
    Represents the ID of an UKCI model.
    """

    def get_json_file(self) -> str:
        """
        Returns the json file name for a model containing the model ID as identifier.

        :return: Json file name for the model with current ID
        :rtype: str
        """
        return "{}.json".format(self.value)

    HadGEM3_GC31_LL = "HadGEM3-GC31-LL"


class UKCIPlugin(BasePlugin):
    def __init__(self):
        super(UKCIPlugin, self).__init__("UKCI")

    def models_parameters(self, model_id: str) -> ModelParameters:
        models_store = UKCIModelStore.instance()
        return models_store.get(model_id)

    def overload_models_parameters(self, source_dir: str) -> None:
        models_store = UKCIModelStore.instance()
        models_store.overload_params(source_dir)

    def grid_labels(self) -> Type[GridLabel]:
        # Use CMIP6 settings for grid labels
        return Cmip6GridLabel

    def stream_info(self) -> StreamInfo:
        stream_store = UKCIStreamStore.instance()
        return stream_store.get()

    def global_attributes(self, request: "Request") -> Cmip6GlobalAttributes:
        """
        Returns the global attributes for CMIP6. The given request contains all information
        about the global attributes.

        :param request: Dictionary containing information about the global attributes
        :type request: Dict[str, Any]
        :return: Class to store and manage the global attributes for CMIP6
        :rtype: Cmip6GlobalAttributes
        """
        return Cmip6GlobalAttributes(request)

    def model_file_info(self) -> ModelFileInfo:
        return GlobalModelFileInfo()

    def license(self) -> str:
        return UKCI_LICENSE

    def mip_table_dir(self) -> str:
        return "{}/mip_tables/UKCI/for_functional_tests".format(os.environ["CDDS_ETC"])


class HadGEM3_GC31_LL_Params(BaseModelParameters):
    """
    Class to store the parameters for the HadGEM3_GC31_LL model.
    """

    def __init__(self) -> None:
        super(HadGEM3_GC31_LL_Params, self).__init__(UKCIModelId.HadGEM3_GC31_LL)

    @property
    def model_version(self) -> str:
        """
        Returns the model version of the HadGEM3_GC31_LL model.

        :return: Model version of HadGEM3_GC31_LL
        :rtype: str
        """
        return "1.0"

    @property
    def data_request_version(self) -> str:
        """
        Returns the data request version of the HadGEM3_GC31_LL model.

        :return: Data request version of HadGEM3_GC31_LL
        :rtype: str
        """
        return "1.0"

    @property
    def um_version(self) -> str:
        """
        Returns the UM version of the HadGEM3_GC31_LL model.

        :return: UM version of HadGEM3_GC31_LL
        :rtype: str
        """
        return "10.0"


class UKCIModelStore(BaseModelStore):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        models_to_include = [
            HadGEM3_GC31_LL_Params(),
        ]
        super(UKCIModelStore, self).__init__(models_to_include)

    @classmethod
    def create_instance(cls) -> "UKCIModelStore":
        return UKCIModelStore()

    def _load_default_params(self) -> None:
        local_dir = os.path.dirname(os.path.abspath(__file__))
        default_dir = os.path.join(local_dir, "data/model")
        results = self.overload_params(default_dir)
        self._process_load_results(results)

    def _process_load_results(self, results: LoadResults) -> None:
        if results.unloaded:
            template = 'Failed to load model parameters for model "{}" from file: "{}"'
            error_messages = [template.format(model_id, path) for model_id, path in results.unloaded.items()]
            self.logger.warning("\n".join(error_messages))
            raise RuntimeError("\n".join(error_messages))


class UKCIStreamInfo(BaseStreamInfo):
    def __init__(self, config_path: str = "") -> None:
        if not config_path:
            local_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(local_dir, "data/streams/streams_config.json")
        super(UKCIStreamInfo, self).__init__(config_path)


class UKCIStreamStore(BaseStreamStore):
    def __init__(self) -> None:
        stream_info = UKCIStreamInfo()
        super(UKCIStreamStore, self).__init__(stream_info)

    @classmethod
    def create_instance(cls) -> "UKCIStreamStore":
        return UKCIStreamStore()
