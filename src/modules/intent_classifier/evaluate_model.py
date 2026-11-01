import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sentence_transformers import SentenceTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
import json

def run_evaluation():
    # 1. Đọc dữ liệu từ file của bạn
    print("Đang đọc dữ liệu...")
    with open('data/intent_dataset.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts = [item['text'] for item in data]
    labels = [item['label'] for item in data]

    # 2. Chia tập Train / Test (80% Train, 20% Test)
    # stratify=labels giúp đảm bảo tỷ lệ Lớp 1,2,3 ở Train và Test là tương đồng nhau
    X_train_text, X_test_text, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    # 3. Vector hóa văn bản bằng MiniLM
    print("Đang mã hóa văn bản (Embedding)...")
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
    X_train = embedder.encode(X_train_text)
    X_test = embedder.encode(X_test_text)

    # 4. Huấn luyện mô hình SVM trên tập Train
    print("Đang huấn luyện mô hình SVM...")
    clf = make_pipeline(StandardScaler(), SVC(gamma='auto'))
    clf.fit(X_train, y_train)

    # 5. Yêu cầu mô hình dự đoán trên tập Test (dữ liệu nó chưa từng thấy)
    print("Đang đánh giá mô hình...")
    y_pred = clf.predict(X_test)

    # ==========================================
    # PHẦN XUẤT BÁO CÁO (OUTPUTS CHO ĐỒ ÁN)
    # ==========================================
    target_names = ['Label 1 (RAG)', 'Label 2 (Query)', 'Label 3 (Talk)']

    # A. In bảng chỉ số (Precision, Recall, F1-Score) ra terminal
    print("\n" + "="*50)
    print("BẢNG BÁO CÁO ĐÁNH GIÁ MÔ HÌNH - INTENT CLASSIFIER")
    print("="*50)
    print(classification_report(y_test, y_pred, target_names=target_names))

    # B. Vẽ Ma trận nhầm lẫn (Confusion Matrix)
    cm = confusion_matrix(y_test, y_pred)
    
    # Thiết lập khung hình đồ thị
    plt.figure(figsize=(8, 6))
    # Sử dụng seaborn heatmap để làm đẹp ma trận
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=target_names, yticklabels=target_names,
                annot_kws={"size": 14}) # Tăng kích thước số
    
    # Trang trí đồ thị
    plt.xlabel('Intent mô hình dự đoán', fontsize=12, fontweight='bold')
    plt.ylabel('Intent thực tế', fontsize=12, fontweight='bold')
    plt.title('Ma trận nhầm lẫn - Intent Classifier', fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    
    # Lưu ra file ảnh để chèn vào báo cáo
    plt.savefig('confusion_matrix_report.png', dpi=300) # dpi=300 cho ảnh nét căng
    print("\n-> Đã lưu ảnh ma trận nhầm lẫn thành công tại: 'confusion_matrix_report.png'")
    
    # Hiển thị ảnh lên màn hình
    plt.show()

if __name__ == "__main__":
    run_evaluation()