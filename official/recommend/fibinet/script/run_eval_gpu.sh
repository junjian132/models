#!/bin/bash
# Copyright 2022 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================

echo "=============================================================================================================="
echo "Please run the script as: "
echo "bash run_eval_gpu.sh"
echo "         "
echo "If your data_path or device_id or device_target is different from those in default_config.yaml, "
echo "please run the script as: "
echo "bash run_eval_gpu.sh DATA_PATH DEVICE_ID DEVICE_TARGET"
echo "for example: bash ./script/run_eval_gpu.sh './data/mindrecord/' 1 GPU "
echo "         "
echo "**** FYI: only DEVICE_TARGET=GPU is supported currently. ****"
echo "         "
echo "Then you can find detailed log and results in files: eval_output.log, eval.log and loss.log. "
echo "         "
echo "If you want to set up more parameters by yourself, "
echo "you are suggested to check the file default_config.yaml and change parameter values there. "
echo "=============================================================================================================="

DATA_PATH=$1
DEVICE_ID=$2
DEVICE_TARGET=GPU


export CUDA_VISIBLE_DEVICES=$DEVICE_ID
python ./eval.py --data_path=$DATA_PATH --device_target=$DEVICE_TARGET > eval_output.log 2>&1 &
