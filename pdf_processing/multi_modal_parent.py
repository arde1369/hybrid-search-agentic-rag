from abc import ABC
import torch

class MultiModalParent(ABC):

    # embedding function for text
    def embed_text(self, text):
        """Embed text using CLIP."""
        inputs = self.clip_processor(
            text=text, 
            return_tensors="pt", 
            padding=True,
            truncation=True,
            max_length=77  # CLIP's max token length
        )
        with torch.no_grad():
            outputs = self.clip_model.get_text_features(**inputs)
            # FIX: BaseModelOutputWithPooling is a container; extract the tensor
            # We use .pooler_output or simply index [0]
            text_features = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
            
            # Normalize embeddings
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            return text_features.squeeze().cpu().numpy()