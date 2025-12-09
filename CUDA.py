import torch
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Використовується пристрій: {device}")
print(f"Назва GPU: {torch.cuda.get_device_name(0)}")