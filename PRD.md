### **项目名称：GRE 单词永动机 V2.0**

### 1. 项目愿景与设计哲学

*   **核心目标：** 创建一个全自动、智能化的 GRE 单词复习与收集系统。
*   **设计哲学：**
    *   **最小化依赖：** 只使用最轻量、最普遍的工具（Python, Flask, CSV, Cron）。
    *   **模块化：** 将单词收集（Web UI）、智能复习（核心逻辑）、定时推送（Cron + Push）和数据存储（CSV）四个部分清晰解耦。
    *   **易于维护：** 即使是不懂编程的人，也能通过编辑文本文件来管理单词库。

### 2. 项目架构与技术栈

| 组件           | 技术选型               | 作用                                                         |
| :------------- | :--------------------- | :----------------------------------------------------------- |
| **Web 前端**   | Flask, HTML/CSS        | 提供一个简单的网页，用于随时随地添加新单词。                 |
| **后端逻辑**   | Python                 | 实现艾宾浩斯记忆曲线算法，处理数据，发送推送。               |
| **Web 服务器** | Gunicorn               | 一个简单、高效的 Python WSGI 服务器，用于在生产环境中运行 Flask 应用。 |
| **数据存储**   | CSV 文件 (`words.csv`) | 零配置的数据库，存储单词、释义和复习状态。                   |
| **推送服务**   | ntfy.sh                | 零配置、无需注册的手机消息推送服务。                         |
| **任务调度**   | Cron                   | Linux 系统自带的守护进程，用于定时执行复习推送脚本。         |
| **进程管理**   | systemd                | Linux 系统标准工具，用于确保 Web 应用在后台长期稳定运行。    |

#### **项目文件结构**

```
/home/your_user/gre_word_pusher/
├── app.py             # Flask Web 应用，用于添加单词
├── push_words.py      # 核心推送脚本，包含艾宾浩斯算法
├── words.csv          # 单词数据库
├── templates/
│   └── index.html     # Web 界面的 HTML 文件
└── gre_app.service    # (部署用) Systemd 服务配置文件
```

---

### 3. 分步开发与部署指南

#### **第 1 步：环境准备 (预计 20 分钟)**

1.  SSH 登录你的 VPS。
2.  创建项目目录：
    ```bash
    mkdir -p /home/your_user/gre_word_pusher/templates
    cd /home/your_user/gre_word_pusher
    ```
3.  安装所有必要的 Python 包：
    ```bash
    pip3 install Flask gunicorn requests
    ```
4.  在手机上安装并配置 `ntfy` (同 V1.0，确保你有一个私密的 Topic Name)。

#### **第 2 步：升级数据结构与艾宾浩斯算法 (核心)**

我们的 `words.csv` 文件格式保持不变，但我们将赋予 `review_count` 和 `last_reviewed_date` 新的含义。
`word,definition,added_date,last_reviewed_date,review_count`

*   `review_count`：现在代表**记忆阶段**（Level）。0 代表新词，1 代表已复习1次，以此类推。
*   `last_reviewed_date`：上次复习的日期。

我们将基于 `review_count` 来决定下一次复习的时间间隔。

**创建 `push_words.py` (包含艾宾浩斯逻辑):**

```python
# /home/your_user/gre_word_pusher/push_words.py
import csv
import requests
import random
from datetime import date, timedelta, datetime

# --- 配置区 ---
NTFY_TOPIC = "gre-words-for-my-awesome-life-123xyz" # 换成你的 ntfy 主题
CSV_FILE_PATH = "/home/your_user/gre_word_pusher/words.csv"
WORDS_PER_PUSH = 15

# --- 艾宾浩斯记忆曲线间隔 (天) ---
# 分别是：新词(0), 复习1次后, 复习2次后, ...
# 第0阶段(新词)实际上是立即复习，这里用1天作为首次复习间隔
REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30, 60] 

def get_review_words(file_path, num_words):
    """
    基于艾宾浩斯记忆曲线挑选单词。
    优先级: 1. 新词 (review_count=0)  2. 到达复习日期的词
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            all_words = list(csv.reader(f))
    except FileNotFoundError:
        return [], []

    if not all_words:
        return [], []

    today = date.today()
    words_to_review = []
    
    # 1. 筛选出所有新词和到期的词
    due_words = []
    for i, row in enumerate(all_words):
        try:
            word, definition, added_date, last_reviewed_date, review_count_str = row
            review_count = int(review_count_str)
            
            # 优先处理新词 (假设添加当天就应该被看到，所以也加入复习列表)
            if review_count == 0:
                due_words.append((row, -999, i)) # 用-999保证新词排序最前
                continue

            # 计算下一次复习日期
            last_review_dt = datetime.strptime(last_reviewed_date, '%Y-%m-%d').date()
            # 获取当前阶段对应的间隔天数，如果超出预设则使用最后一个间隔
            interval_days = REVIEW_INTERVALS[min(review_count, len(REVIEW_INTERVALS) - 1)]
            next_review_date = last_review_dt + timedelta(days=interval_days)

            if today >= next_review_date:
                days_overdue = (today - next_review_date).days
                due_words.append((row, days_overdue, i)) # 记录原始索引
        except (ValueError, IndexError) as e:
            print(f"警告: 跳过格式错误的行 {i+1}: {row}. 错误: {e}")
            continue

    # 2. 排序：最逾期的 > 新词 > 刚到期的
    due_words.sort(key=lambda x: x[1], reverse=True)
    
    # 3. 提取要复习的单词列表和它们的原始索引
    words_to_review_with_indices = due_words[:num_words]
    words_to_review = [item[0] for item in words_to_review_with_indices]
    original_indices = {item[2] for item in words_to_review_with_indices}

    return words_to_review, all_words, original_indices

def update_and_save_words(file_path, all_words, reviewed_indices):
    """更新复习过的单词的状态并写回文件"""
    today_str = date.today().isoformat()
    for i, row in enumerate(all_words):
        if i in reviewed_indices:
            row[3] = today_str  # 更新上次复习日期
            row[4] = str(int(row[4]) + 1) # 记忆阶段+1
    
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(all_words)

def send_notification(topic, words_to_review):
    # (此函数与 V1.0 版本完全相同，此处为简洁省略)
    # ... 只是确保它在这里被定义或导入 ...
    if not words_to_review:
        print("没有需要复习的单词。")
        return
    message_lines = [f"{word}: {definition}" for word, definition, *_ in words_to_review]
    message = "\n".join(message_lines)
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode('utf-8'),
            headers={"Title": "GRE 单词复习！(智能版)", "Priority": "high", "Tags": "brain"}
        )
        print(f"成功发送 {len(words_to_review)} 个单词到 ntfy 主题: {topic}")
    except requests.exceptions.RequestException as e:
        print(f"发送 ntfy 推送失败: {e}")

if __name__ == "__main__":
    review_list, all_data, reviewed_idx = get_review_words(CSV_FILE_PATH, WORDS_PER_PUSH)
    send_notification(NTFY_TOPIC, review_list)
    if review_list:
        update_and_save_words(CSV_FILE_PATH, all_data, reviewed_idx)
```

#### **第 3 步：构建 Web 界面用于添加单词 (预计 1 小时)**

**1. 创建 HTML 模板 (`templates/index.html`):**

```html
<!-- /home/your_user/gre_word_pusher/templates/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>添加新 GRE 单词</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f4f4f9; color: #333; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 90%; max-width: 400px; }
        h1 { text-align: center; color: #5a67d8; }
        form { display: flex; flex-direction: column; gap: 1rem; }
        input { padding: 0.8rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem; }
        button { padding: 0.8rem; background-color: #5a67d8; color: white; border: none; border-radius: 4px; font-size: 1rem; cursor: pointer; transition: background-color 0.2s; }
        button:hover { background-color: #434190; }
        .flash { padding: 1rem; margin-bottom: 1rem; border-radius: 4px; text-align: center; }
        .success { background-color: #d1fae5; color: #065f46; }
    </style>
</head>
<body>
    <div class="container">
        <h1>添加新单词</h1>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash success">{{ messages[0] }}</div>
            {% endif %}
        {% endwith %}
        <form method="post">
            <input type="text" name="word" placeholder="新单词" required>
            <input type="text" name="definition" placeholder="中文释义" required>
            <button type="submit">添加到单词库</button>
        </form>
    </div>
</body>
</html>
```

**2. 创建 Flask 应用 (`app.py`):**

```python
# /home/your_user/gre_word_pusher/app.py
from flask import Flask, request, render_template, redirect, url_for, flash
import csv
from datetime import date

app = Flask(__name__)
# 需要设置一个 secret_key 来使用 flash 消息
app.secret_key = 'a-very-secret-and-random-key-change-me' 

CSV_FILE_PATH = "/home/your_user/gre_word_pusher/words.csv"

def add_word_to_csv(word, definition):
    """向 CSV 文件追加一个新单词"""
    today_str = date.today().isoformat()
    # 新单词格式: word,definition,added_date,last_reviewed_date,review_count
    # last_reviewed_date 初始化为添加日期，review_count 为 0
    new_row = [word, definition, today_str, today_str, 0]
    
    try:
        with open(CSV_FILE_PATH, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(new_row)
        return True
    except Exception as e:
        print(f"写入 CSV 文件失败: {e}")
        return False

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        word = request.form.get('word')
        definition = request.form.get('definition')
        
        if word and definition:
            # 防止添加重复单词（简单检查）
            with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                if any(row[0].lower() == word.lower() for row in reader):
                    flash(f"单词 '{word}' 已存在！")
                    return redirect(url_for('index'))

            if add_word_to_csv(word, definition):
                flash(f"成功添加单词: {word}")
            else:
                flash("添加失败，请检查服务器日志。")
        else:
            flash("单词和释义均不能为空。")
            
        return redirect(url_for('index'))

    return render_template('index.html')

if __name__ == '__main__':
    # 这个仅用于本地测试，生产环境请使用 Gunicorn
    app.run(host='0.0.0.0', port=5000, debug=True)
```
**注意：** 请务必修改 `app.secret_key` 的值为一个你自己的随机字符串。

#### **第 4 步：部署与自动化 (预计 30 分钟)**

我们现在有两个需要运行的程序：定时运行的 `push_words.py` 和长期运行的 `app.py`。

**1. 部署单词推送脚本 (使用 Cron)**

这和 V1.0 完全一样。

```bash
crontab -e
```
设置在每天早上10点开始每两个小时进行一次推送，直到晚上十点
*   我们增加了 `>> /home/your_user/gre_word_pusher/cron.log 2>&1`，这会将脚本的所有输出（包括错误）都记录到 `cron.log` 文件中，便于排查问题。

**2. 部署 Web 应用 (使用 Gunicorn + systemd)**

我们不能用 `python app.py` 来长期运行 Web 应用，因为它会在你关闭 SSH 连接后终止。我们需要一个真正的应用服务器（Gunicorn）和一个进程管理器（systemd）。

首先，测试 Gunicorn 是否能正常工作：
```bash
# 在 /home/your_user/gre_word_pusher/ 目录下运行
gunicorn --workers 1 --bind 0.0.0.0:8000 app:app
```
访问 `http://你的VPS的IP地址:8000`，你应该能看到你的单词添加页面。按 `Ctrl+C` 停止它。

现在，我们用 `systemd` 让它在后台永久运行。

**创建 `systemd` 服务文件:**
```bash
sudo nano /etc/systemd/system/gre_app.service
```
将以下内容粘贴进去。**请确保将 `your_user` 替换为你的实际用户名。**

```ini
[Unit]
Description=Gunicorn instance to serve GRE word adder app
After=network.target

[Service]
User=your_user
Group=www-data # 在某些系统上可能是 nginx 或 apache，www-data 比较通用
WorkingDirectory=/home/your_user/gre_word_pusher
ExecStart=/usr/bin/gunicorn --workers 1 --bind 0.0.0.0:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**启动并授权服务：**

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload
# 启动你的应用
sudo systemctl start gre_app.service
# 设置开机自启
sudo systemctl enable gre_app.service
# 检查服务状态
sudo systemctl status gre_app.service
```
如果状态显示 `active (running)`，恭喜你，Web 应用已成功部署！你可以随时通过 `http://你的VPS的IP地址:8000` 访问它来添加新词了。

### 5. 未来可拓展方向

*   **Telegram Bot 集成:** 当前的架构极易扩展。你可以编写一个简单的 Telegram Bot 脚本，当收到消息时，它也调用 `add_word_to_csv` 函数来添加单词。推送部分，只需在 `send_notification` 函数中，将 `requests.post` 到 ntfy 的代码替换或补充为发送 Telegram 消息的代码即可。核心逻辑完全复用。
*   **Web 界面展示单词:** 可以在 `app.py` 中增加一个新的路由，如 `/list`，用于读取并展示 `words.csv` 中的所有单词及其复习状态。
