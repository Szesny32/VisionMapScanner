from layer.base_layer import BaseLayer

class CameraLayer(BaseLayer):
    def __init__(self, camera_name, data_name):
        super().__init__(camera_name)
        self.data_name = data_name

    def process(self, data):
        self.context['image'] = data.get(self.data_name)

    def draw(self, data):
        return self.context.get('image', None)