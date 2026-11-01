from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.svm import SVC
import numpy as np
import joblib
import json
import os

# Định nghĩa đường dẫn lưu model để không phải train lại mỗi lần khởi động
MODEL_PATH = "src/modules/intent_classifier/model_storage/intent_classifier.pkl"
DATASET_PATH = "src/modules/intent_classifier/data/intent_dataset.json"

class IntentClassifier():
    def __init__(self):
        print("Loading Embedding Model for Intent Classification...")
        # Model nhỏ gọn, chạy cực nhanh trên CPU
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.clf = None
        
        # Load model đã train nếu có, nếu không thì train mới
        if os.path.exists(MODEL_PATH):
            print("Loading existing intent model...")
            self.clf = joblib.load(MODEL_PATH)
        else:
            print("No existing model found. Please train the model first.")
            self.train()

    def train(self):
        """Huấn luyện mô hình phân loại dựa trên dataset"""
        print("Starting training process...")
        
        # 1. Load Dataset
        if not os.path.exists(DATASET_PATH):
            raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}")
            
        with open(DATASET_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        texts = [item['text'] for item in data]
        labels = [item['label'] for item in data]
        
        # 2. Convert Text to Vector (Embeddings)
        print("Encoding texts to vectors...")
        embeddings = self.embedder.encode(texts)
        
        # 3. Train Classifier (Support Vector Machine - SVM)
        # SVM hoạt động rất tốt với dữ liệu ít (few-shot) và không gian vector chiều cao
        print("Fitting SVM classifier...")
        clf = make_pipeline(StandardScaler(), SVC(gamma='auto', probability=True))
        clf.fit(embeddings, labels)
        
        # 4. Save Model
        joblib.dump(clf, MODEL_PATH)
        self.clf = clf
        print("Training completed and model saved.")

    def predict(self, text: str):
        """Dự đoán Intent của câu hỏi"""
        if self.clf is None:
            # Fallback nếu chưa có model
            self.train() 

        # 1. Vector hóa câu hỏi mới
        embedding = self.embedder.encode([text])
        
        # 2. Dự đoán
        # Lấy xác suất (probability) để kiểm tra độ tự tin
        # Lấy xác suất của từng class [prob_class_1, prob_class_2, prob_class_3]
        # Ví dụ: [0.2, 0.75, 0.05]
        probs = self.clf.predict_proba(embedding)[0]
        
        # Lấy nhãn của các class (để map đúng index với label thực tế 1, 2, 3)
        classes = self.clf.classes_
        
        # Tìm class có xác suất cao nhất
        max_prob_index = np.argmax(probs)
        predicted_label = classes[max_prob_index]
        max_prob = probs[max_prob_index]
        
        print(f"Probabilities: {dict(zip(classes, probs))}")
        
        # --- FALLBACK ---
        
        # NGƯỠNG AN TOÀN (Threshold):
        # Chỉ khi model CỰC KỲ CHẮC CHẮN (> 0.75) đó là hỏi DB (2) hoặc Talk (3) thì mới cho đi.
        # Còn lại nếu lấp lửng, cứ đẩy về RAG (1) để tìm trong tài liệu.
        
        CONFIDENCE_THRESHOLD = 0.75
        
        if predicted_label in [2, 3]:
            if max_prob >= CONFIDENCE_THRESHOLD:
                return int(predicted_label)
            else:
                print(f"Confidence for Class {predicted_label} is {max_prob:.2f} (Low) -> Fallback to RAG (1)")
                return 1
        
        # Nếu model dự đoán là 1, thì trả về 1 luôn
        return 1

class IntentClassifierSingleton():
    _instance = None
    
    @staticmethod
    def get():
        if IntentClassifierSingleton._instance is None:
            print("Khởi tạo IntentClassifier lần đầu tiên...")
            IntentClassifierSingleton._instance = IntentClassifier()
        return IntentClassifierSingleton._instance