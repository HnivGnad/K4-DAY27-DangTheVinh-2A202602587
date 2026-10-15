# Reflection

**Sinh viên:** Đặng Thế Vinh — **MSV:** 2A202602587 (làm cá nhân)

**Những loại lỗi khó phát hiện nhất và nguyên nhân**

Các lỗi có độ lệch nhỏ ở feature, phân phối dữ liệu và độ mới của corpus khó phân biệt với dao động bình thường. Baseline được hiệu chuẩn ở mức trung bình ±3σ nên phát hiện tốt lỗi lớn nhưng có thể bỏ sót lỗi nằm trong biên. Logic sử dụng các ngưỡng công bố và bổ sung cảnh báo khi cả số dòng lẫn giá trị trung bình cùng lệch quá 2σ. Đây là tín hiệu hỗ trợ, không bảo đảm phát hiện mọi lỗi nhỏ.

Với lineage, ưu tiên so sánh upstream thực tế với upstream khai báo nếu payload có trường này. Khi không có, học số upstream phổ biến theo transform/job từ các sự kiện đã nhận; đồng thời kiểm tra output bị mồ côi và thời gian chạy. Cách học trực tuyến cần giai đoạn khởi động, có thể nhầm khi topology thay đổi hợp lệ, và không nhận biết được việc thay thế upstream nếu số cạnh không đổi.

**Đánh đổi chi phí và độ bao phủ**

Mỗi sự kiện dùng tối đa một công cụ đo tương ứng; không gọi thêm công cụ để kiểm tra lại cùng sự kiện. Thử nghiệm public cho thấy dừng ngay khi hết ngân sách đạt 43,09 điểm, trong khi cho phép vượt ngân sách có giới hạn đạt 45,12 điểm. Phiên bản cuối giới hạn tổng chi phí ở 1,5 lần ngân sách ban đầu, tương ứng mức phạt chi phí tối đa 10 điểm theo công thức đề bài. Khi công cụ trả lỗi hoặc không còn hạn mức, handler không cảnh báo vì chưa có bằng chứng, nên có thể bỏ sót lỗi.

Kết quả cuối: practice đạt 50,00 điểm, phát hiện 33/33 lỗi, không báo động giả, chi phí 180/220 credits. Public đạt 45,12 điểm, TPR 94,87%, FPR 1,65%, chi phí 240/220. Private đạt 31,48 điểm, TPR 62,96%, FPR 0%, không vượt ngân sách theo báo cáo harness. Kết quả private cho thấy còn bỏ sót nhiều lỗi tinh vi; không suy ra loại lỗi cụ thể vì báo cáo không cung cấp chi tiết. Logic được giữ nguyên sau lần chạy private.

Nếu cải tiến tiếp, tôi sẽ dùng thống kê robust theo từng nguồn trên cửa sổ trượt để bổ sung baseline, kiểm soát việc dữ liệu lỗi làm nhiễm thống kê, và phân bổ lượt đo theo chi phí cùng độ bất định thay vì chỉ giới hạn tổng chi phí. Các thay đổi cần đánh giá trên luồng độc lập để tránh tối ưu theo một seed. Selfcheck và 4 kiểm thử hành vi offline đã chạy thành công.
