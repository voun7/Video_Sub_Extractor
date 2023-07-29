# copyright (c) 2020 PaddlePaddle Authors. All Rights Reserve.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import sys
import tarfile

import requests

from utilities.utils import print_progress


def download_with_progressbar(url, save_path):
    logger = logging.getLogger(__name__)
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        total_size_in_bytes = int(response.headers.get('content-length', 1))
        block_size = 1024  # 1 Kibibyte
        data_progress = 0
        with open(save_path, 'wb') as file:
            for data in response.iter_content(block_size):
                data_progress += block_size
                print_progress(data_progress, total_size_in_bytes, "Downloading model")
                file.write(data)
    else:
        logger.error("Something went wrong while downloading models")
        sys.exit(0)


def maybe_download(model_storage_directory, url):
    # using custom model
    tar_file_name_list = ['.pdiparams', '.pdiparams.info', '.pdmodel']
    if not os.path.exists(
            os.path.join(model_storage_directory, 'inference.pdiparams')
    ) or not os.path.exists(
        os.path.join(model_storage_directory, 'inference.pdmodel')):
        assert url.endswith('.tar'), 'Only supports tar compressed package'
        tmp_path = os.path.join(model_storage_directory, url.split('/')[-1])
        print('download {} to {}'.format(url, tmp_path))
        os.makedirs(model_storage_directory, exist_ok=True)
        download_with_progressbar(url, tmp_path)
        with tarfile.open(tmp_path, 'r') as tarObj:
            for member in tarObj.getmembers():
                filename = None
                for tar_file_name in tar_file_name_list:
                    if member.name.endswith(tar_file_name):
                        filename = 'inference' + tar_file_name
                if filename is None:
                    continue
                file = tarObj.extractfile(member)
                with open(
                        os.path.join(model_storage_directory, filename),
                        'wb') as f:
                    f.write(file.read())
        os.remove(tmp_path)


def is_link(s):
    return s is not None and s.startswith('http')


def confirm_model_dir_url(model_dir, default_model_dir, default_url):
    url = default_url
    if model_dir is None or is_link(model_dir):
        if is_link(model_dir):
            url = model_dir
        file_name = url.split('/')[-1][:-4]
        model_dir = default_model_dir
        model_dir = os.path.join(model_dir, file_name)
    return model_dir, url