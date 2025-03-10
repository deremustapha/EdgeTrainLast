import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from torchvision.models import mobilenet_v3_small
# import convolution
# from mcunet.mcunet.model_zoo import net_id_list, build_model, download_tflite

class EMGNet(nn.Module):
    def __init__(self, num_gesture):
        super(EMGNet, self).__init__()

        self.num_gesture = num_gesture

        self.conv1 = nn.Conv2d(1, 32, kernel_size=3)
        self.layerNorm1 = nn.LayerNorm((32, 6, 38)) # [C, H, W]
        self.conv2 = nn.Conv2d(32, 32, kernel_size=3)
        self.maxpool2 = nn.MaxPool2d(kernel_size=(2, 2), stride=(2, 2))
        self.batchnorm1 = nn.BatchNorm2d(32)
        self.dropout = nn.Dropout(0.5)
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(1152, 151) #1280,40
        self.fc2 = nn.Linear(151, self.num_gesture)
    
    def forward(self, x):
        x = F.relu(self.conv1(x))
        #print(x.shape)
        x = self.layerNorm1(x)
        #x = self.batchnorm1(x)
        x = F.relu(self.conv2(x))
        
        x = self.maxpool2(x)
        x = self.dropout(x)
        x = self.flatten(x)
        # x = self.batchnorm1(x)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x



class FANLayer(nn.Module):

    
    def __init__(self, input_dim, output_dim, p_ratio=0.25):
        super(FANLayer, self).__init__()
        
        # Ensure the p_ratio is within a valid range
        assert 0 < p_ratio < 0.5, "p_ratio must be between 0 and 0.5"
        
        self.p_ratio = p_ratio
        p_output_dim = int(output_dim * self.p_ratio)
        g_output_dim = output_dim - p_output_dim * 2  # Account for cosine and sine terms

        # Linear transformation for the p component (for cosine and sine parts)
        #self.input_linear_p = BinarizeLinear(input_dim, p_output_dim)
        self.input_linear_p = nn.Linear(input_dim, p_output_dim)
        
        # Linear transformation for the g component
        #self.input_linear_g = BinarizeLinear(input_dim, g_output_dim)
        self.input_linear_g = nn.Linear(input_dim, g_output_dim)

        #self.activation = nn.Hardtanh()
        self.activation = nn.GELU()
        

    def forward(self, src):
        """
        Args:
            src (Tensor): Input tensor of shape (batch_size, input_dim).
        
        Returns:
            Tensor: Output tensor of shape (batch_size, output_dim), after applying the FAN layer.
        """
        
        # Apply the linear transformation followed by the activation for the g component

        g = self.activation(self.input_linear_g(src))
        
        # Apply the linear transformation for the p component
        p = self.input_linear_p(src)

        # Concatenate cos(p), sin(p), and activated g along the last dimension
        output = torch.cat((torch.cos(p), torch.sin(p), g), dim=-1)

        
        return output



class EMGFAN(nn.Module):
    def __init__(self, input_dim=1, output_dim=7, similarparameter=False):
        super(EMGFAN, self).__init__()
        self.similarparameter = similarparameter
        self.out_gesture = output_dim
        self.in_channel = input_dim

        self.conv1 = nn.Conv2d(self.in_channel, 32, kernel_size=3)
        self.conv2 = nn.Conv2d(32, 32, kernel_size=3)
        self.batchnorm1 = nn.BatchNorm2d(32)
        self.maxpool2 = nn.MaxPool2d(kernel_size=(2, 2), stride=(2, 2))
        self.dropout = nn.Dropout(0.5)
        self.flatten = nn.Flatten()
        self.scalar = lambda x: x*4//3 if self.similarparameter else x
        self.FAN = FANLayer(576, self.scalar(256)) #1152
        self.fc2 = nn.Linear(256, self.out_gesture)
    
    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = self.batchnorm1(x)
        x = self.maxpool2(x)
        x = self.dropout(x)
        x = self.flatten(x)
        x = self.FAN(x)
        x = self.fc2(x)
        return x




def binarize(tensor):
    return tensor.sign()

class BinarizeLinear(nn.Linear):
    def __init__(self, in_features, out_features):
        super(BinarizeLinear, self).__init__(in_features, out_features)

    def forward(self, input):
        # input * weight
        
        # binarize input
        input.data = binarize(input.data) # Binarize the tensor

        # binarize weight
        if not hasattr(self.weight, 'org'):
            self.weight.org = self.weight.data.clone()
            
        self.weight.data = binarize(self.weight.org)

        res = nn.functional.linear(input, self.weight)

        return res


class BinarizeConv(nn.Conv2d):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1,
                 padding=0, dilation=1, groups=1, bias=True):
        super(BinarizeConv, self).__init__(in_channels, out_channels, kernel_size, stride,
                                           padding, dilation, groups, bias)

    def forward(self, input):
        # input * weight
        
        # binarize input
        input.data = binarize(input.data) # Binarize the tensor

        # binarize weight
        if not hasattr(self.weight, 'org'):
            self.weight.org = self.weight.data.clone()
            
        self.weight.data = binarize(self.weight.org)

        res = nn.functional.conv2d(input, self.weight)

        return res



class EMGFANNew(nn.Module):
    def __init__(self, input_dim=1, output_dim=7, similarparameter=False):
        super(EMGFANNew, self).__init__()
        self.similarparameter = similarparameter
        self.out_gesture = output_dim
        self.in_channel = input_dim

        self.first = nn.Conv2d(self.in_channel, 32, kernel_size=3)
        self.bn1 = nn.BatchNorm2d(32)
        #self.htanh1 = nn.ReLU()
        self.htanh1 = nn.Hardtanh()
        #self.conv2 = nn.Conv2d(32, 32, kernel_size=3)

        self.conv2 = nn.Conv2d(32, 32, kernel_size=3)
        self.bn2 = nn.BatchNorm2d(32)
        #self.htanh2 = nn.ReLU()
        self.htanh2 = nn.Hardtanh()

        # self.conv3 = nn.Conv2d(32, 32, kernel_size=1)
        # self.bn = nn.BatchNorm2d(32)
        # self.act = nn.ReLU()


        

        self.maxpool2 = nn.MaxPool2d(kernel_size=(2, 2), stride=(2, 2))
        self.dropout = nn.Dropout(0.5)
        self.flatten = nn.Flatten()

        self.scalar = lambda x: x*4//3 if self.similarparameter else x
        self.FAN = FANLayer(576, self.scalar(256))
        self.bn3 = nn.BatchNorm1d(256)
        #self.htanh3 = nn.ReLU()
        self.htanh3 = nn.Hardtanh()

        self.last = nn.Linear(256, self.out_gesture)
    
    def forward(self, x):
        x = self.first(x)
        x = self.bn1(x)
        x = self.htanh1(x)


        x = self.conv2(x)
        x = self.bn2(x)
        x = self.htanh2(x)

        
        x = self.maxpool2(x)
        x = self.dropout(x)


        # x = self.conv3(x)
        # x = self.bn(x)
        # x = self.act(x)

        x = self.flatten(x)

        x = self.FAN(x)
        x = self.bn3(x)
        x = self.htanh3(x)

        x = self.last(x)
        return x





def MobileNetV3Small(number_gestures):
    model = mobilenet_v3_small(pretrained=True)
    model.features[0][0] = nn.Conv2d(1, 16, kernel_size=(3, 3), stride=(2, 2), padding=(1, 1), bias=False)
    model.classifier[3] = nn.Linear(in_features=1024, out_features=number_gestures, bias=True)
    return model


def ProxylessNAS(number_gestures):

    target_platform = "proxyless_cpu"
    model = torch.hub.load('mit-han-lab/ProxylessNAS', target_platform, pretrained=True)
    model.first_conv.conv = nn.Conv2d(1, 40, kernel_size=(3, 3), stride=(2, 2), padding=(1, 1), bias=False)
    model.classifier = nn.Linear(1432, number_gestures)

    return model



class CTRLEMGNet(nn.Module):
    def __init__(self, num_gesture):
        super(CTRLEMGNet, self).__init__()

        self.num_gesture = num_gesture

        self.conv1 = nn.Conv2d(1, 32, kernel_size=1, stride=2)
        self.lstm1 = nn.LSTM(32, 32, 2, batch_first=True)
        self.lstm2 = nn.LSTM(32, 32, 2, batch_first=True)
        self.lstm3 = nn.LSTM(32, 32, 2, batch_first=True)
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(32, 32)
        self.output = nn.Linear(32, self.num_gesture)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        print(x.shape)
        x = self.lstm1(x)
        print(x.shape)
        x = self.lstm2(x)
        print(x.shape)
        x = self.lstm3(x)
        x = self.flatten(x)
        print(x.shape)
        x = F.relu(self.fc1(x))
        x = self.output(x)
        return x
    
class CTRLEMG(nn.Module):
    def __init__(self, input_channels, conv_filters, lstm_hidden_size, lstm_layers, num_classes, stride=10):
        super(CTRLEMG, self).__init__()

        self.conv1d = nn.Conv1d(
            in_channels=input_channels,  # This should match the channel dimension of your input
            out_channels=conv_filters,
            kernel_size=10,
            stride=stride
        )
        self.layer_norm1 = nn.LayerNorm(conv_filters)
        self.relu = nn.ReLU()
        self.lstm = nn.LSTM(
            input_size=conv_filters,
            hidden_size=lstm_hidden_size,
            num_layers=lstm_layers,
            batch_first=True
        )
        self.layer_norm2 = nn.LayerNorm(lstm_hidden_size)
        self.fc = nn.Linear(lstm_hidden_size, num_classes)

    def forward(self, x):
        x = x.squeeze(1)  # Remove the channel dimension (from shape [batch_size, 1, 128, 2256] to [batch_size, 128, 2256])
        # Now the input tensor has the shape [batch_size, 128, 2256]
        x = self.conv1d(x)  # Apply Conv1D
        x = self.layer_norm1(x.permute(0, 2, 1))  # Layer normalization
        x = x.permute(0, 2, 1)
        x = self.relu(x)
        x = x.permute(0, 2, 1)
        x, _ = self.lstm(x)
        x = self.layer_norm2(x)
        x = x[:, -1, :]  # Get the output from the last timestep
        x = self.fc(x)
        return x
    


class EMGNet(nn.Module):
    def __init__(self, out_gesture):
        super(EMGNet, self).__init__()

        self.conv1 = nn.Conv2d(1, 32, kernel_size=3)
        self.conv2 = nn.Conv2d(32, 32, kernel_size=3)
        self.batchnorm1 = nn.BatchNorm2d(32)
        self.maxpool2 = nn.MaxPool2d(kernel_size=(2, 2), stride=(2, 2))
        self.dropout = nn.Dropout(0.5)
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(1152, 256)
        self.fc2 = nn.Linear(256, out_gesture)
    
    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = self.batchnorm1(x)
        x = self.maxpool2(x)
        x = self.dropout(x)
        x = self.flatten(x)
        x = self.fc1(x)
        x = self.fc2(x)
        return x
    

# Example usage:
# model = GestureRecognitionModel(input_dim=128, num_gestures=9)
# input_tensor = torch.randn(32, 128)  # Batch size of 32, input dimension of 128
# output = model(input_tensor)



# def MCUNet():

#     mcunet, _, _ = build_model(net_id="mcunet-in3", pretrained=True)
#     mcunet.first_conv.conv = torch.nn.Conv2d(1, 32, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1), bias=False)
#     mcunet.classifier = torch.nn.Linear(160, 10)

#     return mcunet
