<?php
defined('MOODLE_INTERNAL') || die();

function local_mychatbot_before_standard_html_head() {
    global $PAGE, $USER;
    if (isloggedin() && !isguestuser()) {
        $cssurl = new moodle_url('/local/mychatbot/style.css');
        $PAGE->requires->css($cssurl);
    }
}

function local_mychatbot_before_footer() {
    global $PAGE, $CFG, $USER;
    if (isloggedin() && !isguestuser()) {

        echo   '<div id="chatbot-container" class="col-lg-6 col-md-7 col-12 p-1 no-before no-after d-none">
                    <div id="chatbot-sidebar">
                        <div id="sidebar-empty" class="d-none">
                            <i id="chatbot-lightbulb" class="fa-solid fa-lightbulb text-primary bot-float"></i>
                            <p class="mb-2 font-weight-bold text-secondary small">
                                Bắt đầu trò chuyện với chatbot của bạn!
                            </p>
                            <div class="typing">
                                <span class="dot bg-primary"></span>
                                <span class="dot bg-primary"></span>
                                <span class="dot bg-primary"></span>
                            </div>
                        </div>
                        <div id="sidebar-content" class="d-none">
                        </div>
                    </div>

                    <div id="chat-main-content" class="d-flex flex-column">
                        <div id="chat-header" class="row align-items-center m-0 py-1">
                            <div class="col-3">
                                <button id="sidebar-toggle-btn" class="btn btn-icon-circle" title="Toggle sidebar">
                                    <i class="icon fa fa-bars fa-fw m-0"></i>
                                </button>
                            </div>
                            <div class="col-6 text-center">
                                <h5 id="chat-title" class="m-0 text-light">Moodle Chatbot</h5>
                            </div>
                            <div class="col-3 d-flex justify-content-end">
                                <button id="chatbot-close-btn" class="btn btn-icon-circle" title="Đóng chatbot">
                                    <i class="icon fa fa-xmark fa-fw m-0"></i>
                                </button>
                            </div>
                        </div>

                        <div id="chat-window">
                        </div>

                        <div id="chat-input-area" class="position-relative">
                            <div class="chat-input-wrapper">
                                <textarea id="chat-input" placeholder="Nhập tin nhắn..." rows="1"></textarea>
                                <div id="input-error" class="input-floating-error d-none">
                                    <i class="fas fa-exclamation-circle"></i>
                                    <span></span>
                                    <div class="input-floating-error-arrow"></div>
                                </div>
                            </div>
                                
                            <div id="quiz-options-container" class="quiz-options-panel d-none">
                                <div class="quiz-options-header">
                                    <div class="quiz-options-title">
                                        <p>Tải lên tài liệu và chọn cấu hình mong muốn</p>
                                    </div>

                                    <button id="btn-cancel-quiz-mode" class="quiz-close-btn" title="Hủy tạo Quiz">
                                        <i class="fa-solid fa-xmark"></i>
                                    </button>
                                </div>

                                <label for="quiz-ai-file" class="quiz-upload-area">
                                    <input type="file" id="quiz-ai-file" accept=".txt,.pdf,.docx" hidden>

                                    <div class="quiz-upload-icon">
                                        <i class="fa-solid fa-file-arrow-up"></i>
                                    </div>

                                    <div class="quiz-upload-content">  
                                        <strong>Nhấn để tải tài liệu lên hoặc kéo thả file vào đây</strong>
                                        <small>Hỗ trợ: .pdf • tối đa 10MB</small>
                                    </div>

                                </label>

                                <div id="quiz-selected-file" class="quiz-selected-file d-none">
                                    <div class="quiz-file-info">
                                        <div class="quiz-file-icon">
                                            <i class="fa-solid fa-file-lines"></i>
                                        </div>
                                        <div>
                                            <div id="quiz-file-name" class="quiz-file-name"></div>
                                            <div class="quiz-file-meta">Sẵn sàng tạo câu hỏi</div>
                                        </div>
                                    </div>

                                    <button type="button" id="quiz-remove-file" class="quiz-remove-file">
                                        <i class="fa-solid fa-trash"></i>
                                    </button>
                                </div>

                                <div class="quiz-difficulty-wrapper">
                                    <div class="quiz-difficulty-section">
                                        <div class="quiz-difficulty-header">
                                            <label>Phân bố độ khó</label>
                                            <span id="quiz-total-count">Tổng: 0 câu</span>
                                        </div>

                                        <div class="quiz-difficulty-grid">
                                            <div class="difficulty-item easy">
                                                <div class="difficulty-label">
                                                    <i class="fa-solid fa-face-smile"></i>
                                                    <span>Dễ</span>
                                                </div>
                                                <input type="number" id="quiz-ai-easy" value="0" min="0" max="20">
                                            </div>

                                            <div class="difficulty-item medium">
                                                <div class="difficulty-label">
                                                    <i class="fa-solid fa-face-meh"></i>
                                                    <span>Trung bình</span>
                                                </div>
                                                <input type="number" id="quiz-ai-medium" value="0" min="0" max="20">
                                            </div>

                                            <div class="difficulty-item hard">
                                                <div class="difficulty-label">
                                                    <i class="fa-solid fa-face-frown"></i>
                                                    <span>Khó</span>
                                                </div>
                                                <input type="number" id="quiz-ai-hard" value="0" min="0" max="20">
                                            </div>

                                        </div>
                                    </div>

                                    <div id="quiz-difficulty-error" class="quiz-floating-error d-none">
                                        <i class="fas fa-exclamation-circle"></i>
                                        <span></span>

                                        <div class="quiz-floating-error-arrow"></div>
                                    </div>
                                </div>
                            </div>
                            
                            <div id="chat-input-controls">
                                <div id="chat-actions-container">
                                    <button id="chat-actions-btn" class="btn btn-light btn-icon-circle position-relative" title="Thêm hành động">
                                        <i class="fa-solid fa-plus"></i>
                                        <div id="general-badge" class="notification-badge bg-danger d-none">
                                        </div>
                                    </button>
                                    <div id="chat-actions-menu" class="bg-light rounded d-none">
                                        <button class="chat-action-item btn btn-light border-0" data-action="new_chat">
                                            <i class="icon fa-solid fa-message"></i>
                                            <p>Chat mới</p>
                                        </button>

                                        <button class="chat-action-item btn btn-light border-0 position-relative student-action d-none" data-action="quiz_reminder">
                                            <i class="icon fa-solid fa-list-check text-info"></i>
                                            <p>Nhắc nhở Quiz</p>
                                            <div id="quiz-badge" class="notification-badge bg-danger d-none">
                                            </div>
                                        </button>
                                        <button class="chat-action-item btn btn-light border-0 position-relative student-action d-none" data-action="assignment_reminder">
                                            <i class="icon fa-solid fa-file-circle-check text-info"></i>
                                            <p>Nhắc nhở Assignment</p>
                                            <div id="assignment-badge" class="notification-badge bg-danger d-none">
                                            </div>
                                        </button>

                                        <button class="chat-action-item btn btn-light border-0 teacher-action d-none" data-action="course_progress">
                                            <i class="icon fa-solid fa-chart-line text-info"></i>
                                            <p>Tiến độ khóa học</p>
                                        </button>
                                        <button class="chat-action-item btn btn-light border-0 teacher-action d-none" data-action="create_quiz">
                                            <i class="icon fa-solid fa-wand-magic-sparkles text-warning"></i>
                                            <p>Tạo câu hỏi Quiz</p>
                                        </button>

                                    </div>
                                </div>
                                <button id="send-btn" class="btn btn-secondary btn-icon-circle" title="Gửi tin nhắn">
                                    <i class="fa-solid fa-paper-plane"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                </div>';
        $PAGE->requires->js_call_amd('local_mychatbot/chatbot', 'init', []);
        $PAGE->requires->js_call_amd('local_mychatbot/chatbot', 'injectIcon', []);
        $PAGE->requires->js_call_amd('local_mychatbot/chatbot', 'checkCapability', []);
    }
}

