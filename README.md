# PROMPT-TO-CLI

## 1. Tên đề tài

**Secure Prompt-to-CLI Framework for Network Device Configuration**

Tên ngắn trong repository: **PROMPT-TO-CLI**.

Đề tài xây dựng một prototype giúp chuyển yêu cầu cấu hình mạng bằng ngôn ngữ tự nhiên thành lệnh Cisco IOS CLI, đồng thời bổ sung các lớp bảo vệ để giảm rủi ro khi dùng LLM trong môi trường quản trị thiết bị mạng.

## 2. Mục tiêu của prototype

Prototype này phục vụ nghiên cứu khoa học trong lĩnh vực an toàn thông tin và quản trị mạng. Mục tiêu chính:

- Chuẩn hóa prompt từ các test case cấu hình mạng.
- Ẩn danh dữ liệu nhạy cảm trước khi đưa vào LLM.
- Sinh lệnh Cisco IOS CLI bằng Mock LLM có kết quả xác định.
- Khôi phục dữ liệu đã ẩn danh sau khi sinh CLI.
- Kiểm tra lệnh bằng guardrail trước khi cho phép áp dụng.
- Chỉ đẩy cấu hình an toàn vào EVE-NG thông qua Netmiko.
- Ghi log kết quả thí nghiệm để so sánh các baseline: `raw`, `guardrail`, `full`.
- Tính toán metric phục vụ đánh giá nghiên cứu.

Prototype không nhằm thay thế hệ thống triển khai production. Đây là môi trường thử nghiệm có kiểm soát để đánh giá cách kết hợp LLM, ẩn danh dữ liệu và guardrail trong bài toán cấu hình thiết bị mạng.

## 3. Kiến trúc Secure Prompt-to-CLI Framework

Luồng xử lý tổng quát:

```text
data/testcases.csv
        |
        v
Prompt Builder
        |
        +------------------------------+
        |                              |
        | raw baseline                 | full baseline
        v                              v
Mock LLM                         Data Anonymization
        |                              |
        |                              v
        |                         Mock LLM
        |                              |
        |                              v
        |                         De-anonymization
        |                              |
        +--------------+---------------+
                       |
                       v
                Guardrail Layer
                       |
          +------------+------------+
          |                         |
       Reject                    Accept
          |                         |
          v                         v
   Không đẩy cấu hình         Netmiko Runner
                                    |
                                    v
                              EVE-NG Validator
                                    |
                                    v
                             outputs/results.*
                                    |
                                    v
                                Evaluator
```

Ba baseline trong prototype:

- `raw`: Prompt Builder -> Mock LLM -> ghi kết quả. Baseline này dùng để quan sát output thô, không áp dụng vào EVE-NG.
- `guardrail`: Prompt Builder -> Mock LLM -> Guardrail Layer -> có thể áp dụng vào EVE-NG nếu được `Accept`.
- `full`: Prompt Builder -> Data Anonymization -> Mock LLM -> De-anonymization -> Guardrail Layer -> có thể áp dụng vào EVE-NG nếu được `Accept`.

## 4. Các thành phần chính

### Prompt Builder

File chính: `src/prompt_builder.py`

Prompt Builder đọc từng dòng trong `data/testcases.csv`, chuẩn hóa thành đối tượng test case, sau đó tạo prompt theo cấu trúc cố định gồm:

- Vai trò của assistant cấu hình mạng.
- Instruction yêu cầu sinh Cisco IOS CLI.
- Context: thiết bị, loại task, VLAN ID, VLAN name, interface.
- Intent của người dùng.
- Ràng buộc output: chỉ trả về CLI, không giải thích, không Markdown, không sinh lệnh phá hoại.

### Data Anonymization

File chính: `src/anonymizer.py`

Thành phần này thay thế các giá trị nhạy cảm trong prompt bằng token ổn định, ví dụ:

- Tên thiết bị: `SW1`, `CoreSW01` -> `DEVICE_A`, `DEVICE_B`
- IP hoặc subnet -> `IP_001`, `SUBNET_001`
- Interface -> `INTERFACE_001`
- VLAN name -> `VLAN_NAME_001`

Mapping được lưu trong `data/anonymization_map.json` để có thể khôi phục dữ liệu sau khi Mock LLM sinh CLI.

### De-anonymization

File chính: `src/de_anonymizer.py`

De-anonymization khôi phục token trong output của LLM về giá trị ban đầu dựa trên mapping. Nếu output vẫn còn token chưa khôi phục, pipeline `full` sẽ đánh dấu lỗi để guardrail không vô tình xử lý một cấu hình chưa hoàn chỉnh.

### Mock LLM

File chính: `src/llm_client.py`

Prototype hiện dùng Mock LLM thay vì gọi API LLM thật. Mock LLM sinh CLI theo `expected_task_type` trong test case, ví dụ:

- `vlan_create`: tạo VLAN và đặt tên VLAN.
- `vlan_access`: tạo VLAN, vào interface, cấu hình access VLAN.
- `stp_root`: cấu hình STP root primary.
- `risky`: sinh một lệnh nguy hiểm để kiểm tra khả năng chặn của guardrail.

Việc dùng Mock LLM giúp thí nghiệm có tính lặp lại, dễ kiểm thử và phù hợp cho prototype nghiên cứu.

### Guardrail Layer

File chính: `src/guardrail.py`

Guardrail Layer kiểm tra CLI theo ba nhóm:

- `syntax_pass`: kiểm tra cú pháp Cisco IOS trong phạm vi nghiên cứu VLAN/STP.
- `security_pass`: chặn lệnh nguy hiểm như `reload`, `write erase`, `erase startup-config`, `delete flash:`, `format flash:`, `debug all`.
- `policy_pass`: kiểm tra chính sách nội bộ, topology hợp lệ, interface tồn tại trong `config/topology.yaml`, và các setting an toàn trong `config/settings.yaml`.

Kết quả chính là `Accept` hoặc `Reject`. Chỉ lệnh `Accept` mới có thể đi tiếp đến Netmiko Runner.

### Netmiko Runner

File chính: `src/netmiko_runner.py`

Netmiko Runner kết nối tới thiết bị Cisco IOS trong EVE-NG dựa trên `config/devices.yaml`. Thành phần này:

- Lấy thông tin thiết bị theo tên trong test case.
- Loại bỏ wrapper command như `conf t`, `configure terminal`, `end`, `exit`.
- Chỉ gửi cấu hình khi guardrail cho phép.
- Không áp dụng lệnh `Reject`.
- Không áp dụng lệnh `Warning` nếu `allow_warning_apply=false`.

### EVE-NG Validator

File chính: `src/eve_validator.py`

Sau khi cấu hình được áp dụng, EVE-NG Validator chạy các lệnh `show` để kiểm tra trạng thái thiết bị:

- `show vlan brief` cho task tạo VLAN.
- `show running-config interface <interface>` cho task access VLAN.
- `show spanning-tree vlan <vlan_id>` cho task STP root.

Kết quả validation được ghi vào `outputs/results.csv` và `outputs/results.jsonl`.

### Evaluator

File chính: `src/evaluator.py`

Evaluator đọc kết quả thí nghiệm từ `outputs/results.csv`, nhóm theo baseline và tính các metric như:

- `accept_rate`
- `reject_rate`
- `syntax_validity_rate`
- `security_pass_rate`
- `policy_pass_rate`
- `dangerous_command_rate`
- `guardrail_blocking_rate`
- `leakage_rate`
- `average_latency_ms`

Kết quả tổng hợp được in ra terminal và lưu vào `outputs/metrics_summary.csv`.

## 5. Cấu trúc thư mục

```text
PROMPT-TO-CLI/
├── config/
│   ├── devices.yaml           # Thông tin kết nối thiết bị EVE-NG qua Netmiko
│   ├── guardrail_rules.yaml   # Danh sách lệnh nguy hiểm và ngoài phạm vi
│   ├── settings.yaml          # Cấu hình an toàn cho prototype
│   └── topology.yaml          # Inventory thiết bị/interface và task được phép
├── data/
│   ├── anonymization_map.json # Mapping token ẩn danh <-> giá trị thật
│   └── testcases.csv          # Bộ test case đầu vào cho thí nghiệm
├── outputs/
│   ├── results.csv            # Kết quả chạy baseline
│   ├── results.jsonl          # Kết quả dạng JSON Lines
│   └── metrics_summary.csv    # Metric tổng hợp từ Evaluator
├── prompts/
│   └── prompt_template.txt    # Template prompt tham khảo
├── src/
│   ├── anonymizer.py          # Ẩn danh dữ liệu nhạy cảm
│   ├── config_loader.py       # Đọc CSV/YAML
│   ├── de_anonymizer.py       # Khôi phục token đã ẩn danh
│   ├── evaluator.py           # Tính metric nghiên cứu
│   ├── eve_validator.py       # Kiểm tra trạng thái thiết bị EVE-NG
│   ├── guardrail.py           # Kiểm tra syntax/security/policy
│   ├── llm_client.py          # Mock LLM sinh Cisco IOS CLI
│   ├── logger.py              # Ghi kết quả ra CSV/JSONL
│   ├── main.py                # Entry point chạy thí nghiệm
│   ├── netmiko_runner.py      # Gửi cấu hình qua Netmiko
│   ├── prompt_builder.py      # Chuẩn hóa test case thành prompt
│   └── utils.py               # Hàm tiện ích
├── tests/                     # Unit test và integration-style test
├── requirements.txt           # Thư viện Python cần cài
└── README.md
```

## 6. Cách cài đặt môi trường

Yêu cầu: Python 3.10+ khuyến nghị.

Trên Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Nếu dùng Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 7. Cách chạy test

```powershell
python -m pytest -q -p no:cacheprovider
```

Lệnh này chạy toàn bộ test trong thư mục `tests/` và tắt pytest cache provider để kết quả gọn hơn.

## 8. Cách chạy baseline

Chạy `raw` baseline:

```powershell
python -m src.main --baseline raw --testcases data/testcases.csv
```

Chạy `guardrail` baseline:

```powershell
python -m src.main --baseline guardrail --testcases data/testcases.csv
```

Chạy `full` baseline:

```powershell
python -m src.main --baseline full --testcases data/testcases.csv
```

Kết quả được ghi vào:

- `outputs/results.csv`
- `outputs/results.jsonl`

## 9. Cách chạy evaluator

Sau khi đã chạy một hoặc nhiều baseline, dùng Evaluator để tổng hợp metric:

```powershell
python -m src.evaluator --results outputs/results.csv
```

Evaluator sẽ in bảng metric ra terminal và lưu file:

```text
outputs/metrics_summary.csv
```

## 10. Cách chạy với EVE-NG

Để cho phép pipeline áp dụng cấu hình đã được guardrail chấp nhận vào EVE-NG:

```powershell
python -m src.main --baseline full --testcases data/testcases.csv --apply-to-eve
```

Khuyến nghị chỉ dùng `--apply-to-eve` với baseline `full`, vì baseline này có đủ các bước ẩn danh, khôi phục, guardrail và kiểm tra an toàn trước khi gửi cấu hình.

## 11. Cảnh báo an toàn

Các nguyên tắc an toàn quan trọng:

- Raw baseline never applies to EVE-NG.
- Reject commands are never pushed to switch.
- Warning commands are not applied unless `allow_warning_apply=true`.
- Dangerous commands such as `reload`, `write erase`, `erase startup-config` are blocked.
- Không chạy prototype trên thiết bị production.
- Chỉ thử nghiệm trong lab EVE-NG hoặc môi trường mô phỏng có thể khôi phục trạng thái.
- Kiểm tra kỹ `config/devices.yaml` trước khi bật `--apply-to-eve`.

Trong code hiện tại, baseline `raw` sẽ chỉ sinh và ghi kết quả. Nếu truyền thêm `--apply-to-eve`, chương trình vẫn in cảnh báo an toàn và không đẩy cấu hình raw vào EVE-NG.

## 12. Cách cấu hình `devices.yaml` cho EVE-NG

File cấu hình nằm tại:

```text
config/devices.yaml
```

Ví dụ:

```yaml
SW1:
  device_type: cisco_ios
  host: 192.168.56.101
  username: admin
  password: cisco
  secret: cisco
  port: 22

SW2:
  device_type: cisco_ios
  host: 192.168.56.102
  username: admin
  password: cisco
  secret: cisco
  port: 22
```

Ý nghĩa các trường:

- `SW1`, `SW2`: tên thiết bị, phải trùng với cột `device` trong `data/testcases.csv`.
- `device_type`: loại thiết bị Netmiko, với Cisco IOS thường là `cisco_ios`.
- `host`: địa chỉ IP quản trị của node trong EVE-NG.
- `username`: tài khoản SSH/Telnet.
- `password`: mật khẩu đăng nhập.
- `secret`: enable secret nếu thiết bị cần vào privileged EXEC mode.
- `port`: cổng kết nối, thường là `22` cho SSH.

Checklist trước khi chạy với EVE-NG:

- Thiết bị trong EVE-NG đã boot xong.
- Có thể SSH từ máy chạy prototype tới IP trong `host`.
- Tên thiết bị trong `devices.yaml` khớp với `data/testcases.csv`.
- Interface trong test case tồn tại trong `config/topology.yaml`.
- Lab không trỏ tới thiết bị thật hoặc hệ thống production.

## 13. Giới hạn hiện tại của prototype

Prototype hiện có một số giới hạn:

- Chỉ dùng Mock LLM, chưa tích hợp LLM thật.
- Phạm vi guardrail tập trung vào VLAN, access port và một số cấu hình STP cơ bản.
- Chưa kiểm tra đầy đủ mọi cú pháp Cisco IOS.
- Chưa hỗ trợ rollback tự động nếu cấu hình đã áp dụng nhưng validation thất bại.
- Chưa có cơ chế xác thực mạnh cho secret trong `devices.yaml`; không nên commit thông tin thật.
- Anonymization chỉ bao phủ một số mẫu dữ liệu phổ biến như device name, IP, subnet, interface, VLAN name.
- EVE-NG Validator chỉ kiểm tra một số task type: `vlan_create`, `vlan_access`, `stp_root`.
- Kết quả phụ thuộc vào trạng thái ban đầu của lab EVE-NG.
- Chưa đánh giá chất lượng ngôn ngữ tự nhiên phức tạp như prompt mơ hồ, prompt injection nhiều bước hoặc yêu cầu trái chính sách tinh vi.

## 14. Ý nghĩa của kết quả đối với bài nghiên cứu khoa học

Kết quả từ prototype giúp đánh giá thực nghiệm các câu hỏi nghiên cứu như:

- Guardrail có giảm tỷ lệ lệnh nguy hiểm được sinh ra hoặc được áp dụng hay không?
- Pipeline `full` có giảm rò rỉ thông tin nhạy cảm so với pipeline không ẩn danh hay không?
- Việc thêm guardrail và anonymization ảnh hưởng thế nào đến latency?
- Các baseline khác nhau tạo ra tỷ lệ `Accept`, `Reject`, `dangerous_command_rate`, `leakage_rate` ra sao?
- Khi áp dụng vào EVE-NG, cấu hình được chấp nhận có thật sự tạo ra trạng thái mạng mong muốn hay không?

Trong bài nghiên cứu, có thể dùng:

- `outputs/results.csv` để phân tích từng test case.
- `outputs/results.jsonl` để truy vết chi tiết từng lần chạy.
- `outputs/metrics_summary.csv` để so sánh định lượng giữa các baseline.

Về mặt an toàn thông tin, prototype minh họa rằng không nên đưa output của LLM trực tiếp vào thiết bị mạng. Một framework an toàn hơn cần có ít nhất ba lớp: bảo vệ dữ liệu đầu vào, kiểm soát output sinh ra, và xác thực trạng thái sau khi áp dụng trong môi trường lab.
