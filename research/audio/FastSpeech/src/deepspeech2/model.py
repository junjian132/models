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
"""DeepSpeech2 model."""
import math

import numpy as np
from mindspore import Tensor
from mindspore import nn
from mindspore.ops import operations as P


class SequenceWise(nn.Cell):
    """SequenceWise FC Layers."""
    def __init__(self, module):
        super().__init__()
        self.module = module
        self.reshape_op = P.Reshape()
        self.shape_op = P.Shape()
        self._initialize_weights()

    def construct(self, x):
        sizes = self.shape_op(x)
        t, n = sizes[0], sizes[1]
        x = self.reshape_op(x, (t * n, -1))
        x = self.module(x)
        x = self.reshape_op(x, (t, n, -1))

        return x

    def _initialize_weights(self):
        """Init weights."""
        self.init_parameters_data()
        for _, m in self.cells_and_names():
            if isinstance(m, nn.Dense):
                m.weight.set_data(
                    Tensor(
                        np.random.uniform(
                            -1. / m.in_channels,
                            1. / m.in_channels,
                            m.weight.data.shape
                        ).astype("float32")
                    )
                )

                if m.bias is not None:
                    m.bias.set_data(
                        Tensor(
                            np.random.uniform(
                                -1. / m.in_channels,
                                1. / m.in_channels,
                                m.bias.data.shape).astype("float32")
                        )
                    )


class MaskConv(nn.Cell):
    """
    MaskConv architecture.
    MaskConv is actually not implemented in this part
    because some operation in MindSpore is not supported.
    Lengths is kept for future use.
    """

    def __init__(self):
        super().__init__()
        self.zeros = P.ZerosLike()
        self.conv1 = nn.Conv2d(
            in_channels=1,
            out_channels=32,
            kernel_size=(41, 11),
            stride=(2, 2),
            pad_mode='pad',
            padding=(20, 20, 5, 5)
        )

        self.bn1 = nn.BatchNorm2d(num_features=32)
        self.conv2 = nn.Conv2d(
            in_channels=32,
            out_channels=32,
            kernel_size=(21, 11),
            stride=(2, 1),
            pad_mode='pad',
            padding=(10, 10, 5, 5)
        )

        self.bn2 = nn.BatchNorm2d(num_features=32)
        self.tanh = nn.Tanh()
        self._initialize_weights()
        self.module_list = nn.CellList(
            [
                self.conv1,
                self.bn1,
                self.tanh,
                self.conv2,
                self.bn2,
                self.tanh
            ]
        )

    def construct(self, x):
        for module in self.module_list:
            x = module(x)

        return x

    def _initialize_weights(self):
        """
        parameter initialization
        """
        self.init_parameters_data()
        for _, m in self.cells_and_names():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.set_data(Tensor(np.random.normal(0, np.sqrt(2. / n), m.weight.data.shape).astype("float32")))
                if m.bias is not None:
                    m.bias.set_data(
                        Tensor(np.zeros(m.bias.data.shape, dtype="float32")))
            elif isinstance(m, nn.BatchNorm2d):
                m.gamma.set_data(
                    Tensor(np.ones(m.gamma.data.shape, dtype="float32")))
                m.beta.set_data(
                    Tensor(np.zeros(m.beta.data.shape, dtype="float32")))


class BatchRNN(nn.Cell):
    """
    BatchRNN architecture.

    Args:
        batch_size (int):  Sample_number of per step in training.
        input_size  (int):  Dimension of input tensor.
        hidden_size (int):  Rnn hidden size.
        num_layers (int):  Number of rnn layers.
        bidirectional (bool): Use bidirectional rnn. Currently, only bidirectional rnn is implemented.
        batch_norm(bool): Whether to use BN in RNN.
        rnn_type (str):  Rnn type to use. Currently, only LSTM is supported.
    """

    def __init__(
            self,
            batch_size,
            input_size,
            hidden_size,
            num_layers,
            bidirectional=False,
            batch_norm=False,
            rnn_type='LSTM',
    ):
        super().__init__()
        self.batch_size = batch_size
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.rnn_type = rnn_type
        self.bidirectional = bidirectional
        self.has_bias = True
        self.is_batch_norm = batch_norm
        self.num_directions = 2 if bidirectional else 1
        self.reshape_op = P.Reshape()
        self.shape_op = P.Shape()
        self.sum_op = P.ReduceSum()

        input_size_list = [input_size]
        for i in range(num_layers - 1):
            input_size_list.append(hidden_size)
        layers = []

        for i in range(num_layers):
            layers.append(
                nn.LSTM(
                    input_size=input_size_list[i],
                    hidden_size=hidden_size,
                    bidirectional=bidirectional,
                    has_bias=self.has_bias
                )
            )

        self.lstms = nn.CellList(layers)

        if batch_norm:
            batch_norm_layer = []
            for i in range(num_layers - 1):
                batch_norm_layer.append(nn.BatchNorm1d(hidden_size))
            self.batch_norm_list = batch_norm_layer

    def construct(self, x):
        for i in range(self.num_layers):
            if self.is_batch_norm and i > 0:
                x = self.batch_norm_list[i - 1](x)
            x, _ = self.lstms[i](x)
            if self.bidirectional:
                size = self.shape_op(x)
                x = self.reshape_op(x, (size[0], size[1], 2, -1))
                x = self.sum_op(x, 2)
        return x


class DeepSpeechModel(nn.Cell):
    """
    ResNet architecture.

    Args:
        batch_size (int):  Sample_number of per step in training.
        rnn_type (str):  Rnn type to use.
        labels (str):  Str containing all the possible symbols to map to.
        rnn_hidden_size (int):  Rnn hidden size.
        nb_layers (int):  Number of rnn layers.
        audio_conf: Config containing the sample rate, window and the window length/stride in seconds.
        bidirectional (bool): Use bidirectional rnn.
    """

    def __init__(
            self,
            batch_size,
            labels,
            rnn_hidden_size,
            nb_layers,
            audio_conf,
            rnn_type='LSTM',
            bidirectional=True,
    ):
        super().__init__()
        self.batch_size = batch_size
        self.hidden_size = rnn_hidden_size
        self.hidden_layers = nb_layers
        self.rnn_type = rnn_type
        self.audio_conf = audio_conf
        self.labels = list(labels)
        self.bidirectional = bidirectional
        self.reshape_op = P.Reshape()
        self.shape_op = P.Shape()
        self.transpose_op = P.Transpose()
        self.add = P.Add()
        self.div = P.Div()

        sample_rate = self.audio_conf['sampling_rate']
        window_size = self.audio_conf['window_size']
        num_classes = len(self.labels)

        self.conv = MaskConv()
        # This is to calculate
        self.pre, self.stride = self.get_conv_num()
        self.num_iters = list(range(len(self.stride)))

        # Based on above convolutions and spectrogram size using conv formula (W - F + 2P)/ S+1
        rnn_input_size = int(math.floor((sample_rate * window_size) / 2) + 1)
        rnn_input_size = int(math.floor(rnn_input_size + 2 * 20 - 41) / 2 + 1)
        rnn_input_size = int(math.floor(rnn_input_size + 2 * 10 - 21) / 2 + 1)
        rnn_input_size *= 32

        self.rnn = BatchRNN(
            batch_size=self.batch_size,
            input_size=rnn_input_size,
            num_layers=nb_layers,
            hidden_size=rnn_hidden_size,
            bidirectional=bidirectional,
            batch_norm=False,
            rnn_type=self.rnn_type,
        )

        fully_connected = nn.Dense(rnn_hidden_size, num_classes, has_bias=False)
        self.fc = SequenceWise(fully_connected)

    def construct(self, x, lengths):
        """
        Forward.
        """
        output_lengths = self.get_seq_lens(lengths)
        x = self.conv(x)
        sizes = self.shape_op(x)
        x = self.reshape_op(x, (sizes[0], sizes[1] * sizes[2], sizes[3]))
        x = self.transpose_op(x, (2, 0, 1))
        x = self.rnn(x)

        activations = x.copy()

        x = self.fc(x)

        return x, output_lengths, activations

    def get_seq_lens(self, seq_len):
        """
        Given a 1D Tensor or Variable containing integer sequence lengths,
        return a 1D tensor or variable containing the size sequences
        that will be output by the network.
        """
        for i in self.num_iters:
            seq_len = self.add(self.div(self.add(seq_len, self.pre[i]), self.stride[i]), 1)

        return seq_len

    def get_conv_num(self):
        """Get number of convs."""
        p, s = [], []
        for _, cell in self.conv.cells_and_names():
            if isinstance(cell, nn.Conv2d):
                kernel_size = cell.kernel_size
                padding_1 = int((kernel_size[1] - 1) / 2)
                temp = 2 * padding_1 - cell.dilation[1] * (cell.kernel_size[1] - 1) - 1
                p.append(temp)
                s.append(cell.stride[1])

        return p, s