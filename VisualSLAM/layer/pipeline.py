from collections import defaultdict, deque


class LayerGraph:
    def __init__(self, layers):
        self.layers = list(layers)
        self._ordered = []

    def enabled_layers(self):
        return [l for l in self.layers if l.enabled]

    def get_candidates(self, semantic_key):
        candidates = []
        for layer in self.enabled_layers():
            if semantic_key in layer.provides:
                out_key = layer.provides[semantic_key]
                if out_key is not None:
                    candidates.append((layer.name, out_key))
        return candidates

    def resolve(self):
        enabled = self.enabled_layers()

        provider_lookup = {}
        for provider in enabled:
            for semantic_key, out_key in provider.provides.items():
                if semantic_key not in provider.inputs:
                    provider_lookup.setdefault(out_key, provider)

        for layer in enabled:
            resolved = {}
            for semantic_key in layer.inputs:
                chosen = layer.source_bindings.get(semantic_key)
                if chosen is None:
                    chosen = self._default_binding(enabled, semantic_key)
                resolved[semantic_key] = chosen
            layer.resolved_inputs = resolved

        self._ordered = self._topological_sort(enabled, provider_lookup)
        return self._ordered

    def _default_binding(self, enabled, semantic_key):
        candidates = []
        for provider in enabled:
            if semantic_key in provider.provides:
                out_key = provider.provides[semantic_key]
                if out_key is not None:
                    candidates.append(out_key)

        if not candidates:
            return semantic_key

        for out_key in candidates:
            if out_key == semantic_key:
                return out_key

        return candidates[0]

    def _topological_sort(self, enabled, provider_lookup):
        adjacency = defaultdict(list)
        indegree = {id(layer): 0 for layer in enabled}

        for layer in enabled:
            for semantic_key in layer.inputs:
                out_key = layer.resolved_inputs.get(semantic_key, semantic_key)
                provider = provider_lookup.get(out_key)
                if provider is not None and provider is not layer:
                    if layer not in adjacency[provider]:
                        adjacency[provider].append(layer)
                        indegree[id(layer)] += 1

        queue = deque(l for l in enabled if indegree[id(l)] == 0)
        order = []

        while queue:
            layer = queue.popleft()
            order.append(layer)
            for dependent in adjacency[layer]:
                indegree[id(dependent)] -= 1
                if indegree[id(dependent)] == 0:
                    queue.append(dependent)

        if len(order) != len(enabled):
            raise RuntimeError("Layer dependency cycle detected")

        return order

    def run(self, data):
        self.resolve()

        for layer in self._ordered:
            if layer.skip_if_present and all(o in data for o in layer.outputs):
                continue
            layer.process(data)

        draw_results = {}
        for layer in self.enabled_layers():
            img = layer.draw(data)
            if img is not None:
                draw_results[layer.name] = img
        return draw_results