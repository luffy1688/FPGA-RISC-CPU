"""两个注意力层的小型工具意图模型：训练用 PyTorch，板上用纯整数 C。
这是 Needle-inspired 窄域模型，不是上游 Needle3，也不是通用聊天大模型。
"""
import math
import torch
from torch import nn
import torch.nn.functional as F

TOOLS = ("read_temp", "set_pwm", "run_coremark", "read_counter", "set_led", "reject")
SEQ = 64
ACT_SCALE = 32.0

def ste_round(x):
    """前向取整，反向保留梯度；让训练提前适应 FPGA 的整数运算。"""
    return x + (torch.round(x) - x).detach()

def aq(x):
    return ste_round(torch.clamp(x * ACT_SCALE, -128, 127)) / ACT_SCALE

def wq(weight):
    # 每矩阵使用二的幂缩放；硬件可用移位，不需要浮点乘法。
    maximum = max(float(weight.detach().abs().max()), 1e-6)
    shift = max(-8, min(16, int(math.floor(math.log2(7.0 / maximum)))))
    scale = 2.0 ** (-shift)
    return ste_round(torch.clamp(weight / scale, -8, 7)) * scale

class QLinear(nn.Linear):
    def forward(self, x):
        bias = ste_round(self.bias * ACT_SCALE) / ACT_SCALE
        return F.linear(x, wq(self.weight), bias)

class AttentionBlock(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.d = d_model
        self.heads = 4
        self.q = QLinear(d_model, d_model)
        self.k = QLinear(d_model, d_model)
        self.v = QLinear(d_model, d_model)
        self.o = QLinear(d_model, d_model)
        self.ff1 = QLinear(d_model, d_model * 2)
        self.ff2 = QLinear(d_model * 2, d_model)

    def forward(self, x, length):
        batch, seq, dim = x.shape
        def project(layer):
            return aq(layer(x)).reshape(batch, seq, self.heads, dim // self.heads).transpose(1, 2)
        q, k, v = project(self.q), project(self.k), project(self.v)
        # 固定 /8 缩放。score 是 1/16 的格点，对应 C 端的 exp 查表。
        score = ste_round((q @ k.transpose(-2, -1)) * 2.0) / 16.0
        key_mask = torch.arange(seq, device=x.device)[None, :] >= length[:, None]
        score = score.masked_fill(key_mask[:, None, None, :], -1e4)
        prob = score.softmax(-1)
        context = aq((prob @ v).transpose(1, 2).reshape(batch, seq, dim))
        x = aq((x + aq(self.o(context))) / 2.0)
        ff = aq(F.relu(self.ff1(x)))
        return aq((x + aq(self.ff2(ff))) / 2.0)

class ByteToolModel(nn.Module):
    def __init__(self, d_model=64):
        super().__init__()
        if d_model not in (64, 128):
            raise ValueError("d_model must be 64 (BRAM bring-up) or 128 (DDR profile)")
        self.d = d_model
        self.embedding = nn.Embedding(256, d_model)
        self.position = nn.Embedding(SEQ, d_model)
        self.blocks = nn.ModuleList([AttentionBlock(d_model), AttentionBlock(d_model)])
        self.head = QLinear(d_model, len(TOOLS))
        nn.init.normal_(self.embedding.weight, std=0.35)
        nn.init.normal_(self.position.weight, std=0.05)

    def forward(self, token, length):
        x = F.embedding(token, wq(self.embedding.weight))
        p = wq(self.position.weight)[None, :token.shape[1], :]
        x = aq((x + p) / 2.0)
        for block in self.blocks:
            x = block(x, length)
        mask = torch.arange(token.shape[1], device=x.device)[None, :] < length[:, None]
        pooled = aq((x * mask[:, :, None]).sum(1) / length[:, None])
        # head 保留 INT32 logits，不在分类出口过早夹成 INT8。
        return self.head(pooled)

def tokenize(text):
    raw = list(text.lower().encode("utf-8")[:SEQ])
    if not raw:
        raw = [32]
    return raw + [0] * (SEQ - len(raw)), len(raw)
