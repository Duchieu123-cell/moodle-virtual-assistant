define(['jquery', 'core/ajax', 'core/notification'], function($, ajax, notification) {
    var chatbotContainer = null;
    var chatWindow = null;
    var chatInput = null;
    var sendButton = null;
    var closeButton = null;
    var chatbotIcon = null;
    var chatActionsButton = null;
    var chatActionsMenu = null;
    var sidebar = null;
    var sidebarEmpty = null;
    var sidebarContent = null;
    var sidebarToggleBtn = null;
    var isCheckingStatus = false;
    var currentConversationId = 0;
    var NoConversation = true;
    // BIẾN NÀY ĐỂ QUẢN LÝ TRẠNG THÁI INPUT
    var inputMode = 'chat'; // Giá trị có thể là 'chat' hoặc 'quiz'

    /**
     * Định dạng một Unix timestamp (tính bằng giây)
     * thành chuỗi ngày giờ (ví dụ: "Wed, Dec 4, 8:06 PM")
     * @param {number} timestampInSeconds - Timestamp từ PHP (tính bằng giây)
     */
    function formatTimestamp(timestampInSeconds) {
        const now = new Date(timestampInSeconds * 1000);
        const dateOptions = {
            weekday: 'short',
            month: 'short',
            day: 'numeric'
        };
        const timeOptions = {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        };
        const dateString = now.toLocaleDateString('en-US', dateOptions);
        const timeString = now.toLocaleTimeString('en-US', timeOptions);
        return `${dateString}, ${timeString}`;
    }
    /**
     * Trả về timestamp Unix HIỆN TẠI (tính bằng giây)
     * @returns {number}
     */
    function getCurrentTime() {
        return Math.floor(Date.now() / 1000);
    }
    /**
     * Display welcome message in chat window
     * @param {string} userFullName - User's full name
     */
    function showWelcomeMessage(userFullName) {
        let welcomeMsg = $('<p>')
            .addClass('welcome-message')
            .text(`Xin chào ${userFullName}!`);

        chatWindow.append(welcomeMsg);
    }
    /**
     * Add message to chat window and auto-scroll
     * @param {jQuery} messageElement - jQuery element to append
     * @param {boolean} autoScroll - whether to auto-scroll to bottom, default true
     */
    function appendMessage(messageElement, autoScroll = true) {
        if (chatWindow && chatWindow.length) {
            // 1. Nối element vào cửa sổ chat
            chatWindow.append(messageElement);
            // 2. Tìm bong bóng nội dung thực tế (user-message hoặc bot-message)
            var contentBubble = null;
            if (messageElement.hasClass('user-message-wrapper')) {
                contentBubble = messageElement.find('.user-message');
            } else if (messageElement.hasClass('bot-message-wrapper')) {
                contentBubble = messageElement.find('.bot-message');
            } else {
                // Các trường hợp khác -> bỏ qua
            }
            // 3. Kiểm tra xem có bị tràn (overflow) không
            if (contentBubble && contentBubble.length) {
                var contentEl = contentBubble[0];

                // Dùng setTimeout để đợi trình duyệt tính toán xong chiều cao
                setTimeout(function() {
                    // So sánh chiều cao cuộn (tổng) và chiều cao hiển thị (khả dụng)
                    var isOverflowing = contentEl.scrollHeight > contentEl.clientHeight;
                    if (isOverflowing) {
                        // Thêm class này để kích hoạt gradient CSS
                        contentBubble.addClass('is-overflowing');

                        // 4. Nếu bị tràn, tạo và thêm nút "Mở rộng"
                        var expandBtn = $('<button class="message-expand-btn" title="Hiển thị thêm"></button>');

                        // 5. Thêm sự kiện click cho nút
                        expandBtn.on('click', function(e) {
                            // Ngăn sự kiện click nổi bọt
                            e.stopPropagation();
                            var button = $(this);
                            // Kiểm tra trạng thái trước khi thay đổi
                            var isCurrentlyExpanded = contentBubble.hasClass('expanded');
                            var beforeMessage = contentBubble.outerHeight(true);
                            // Bật/tắt class 'expanded'
                            // CSS sẽ tự động ẨN/HIỆN gradient dựa trên class này
                            contentBubble.toggleClass('expanded');
                            var afterMessage = contentBubble.outerHeight(true);
                            if (isCurrentlyExpanded) {
                                // --- ĐANG THU GỌN ---
                                button.attr('title', 'Hiển thị thêm');
                                // Cuộn để giữ tin nhắn ở trong tầm nhìn
                                chatWindow.scrollTop(chatWindow.scrollTop() - (beforeMessage - afterMessage));
                            } else {
                                // --- ĐANG MỞ RỘNG ---
                                button.attr('title', 'Thu gọn');
                                // Cuộn xuống dưới cùng của tin nhắn đó để đảm bảo tin nhắn mở rộng không bị che
                                chatWindow.scrollTop(chatWindow.scrollTop() - (beforeMessage - afterMessage));
                            }
                        });

                        // 6. Thêm nút vào bên trong bong bóng chat
                        contentBubble.prepend(expandBtn);
                    }
                }, 10); // 10ms thường là đủ
            }
            // 7. Cuộn xuống dưới cùng nếu autoScroll = true
            if (autoScroll) {
                chatWindow.scrollTop(chatWindow.prop("scrollHeight"));
            }
        }
    }
    /**
     * Display system message in chat window
     * @param {string} text - Message text
     * @param {string} type - 'status-ok' or 'status-error' or 'info'
     */
    function showSystemMessage(text, type) {
        const msg = $('<div>').addClass('system-message m-1 p-2')
            .addClass(type);
        const prg = $('<p>').text(text);
        msg.append(prg);
        appendMessage(msg, false);
    }
    /**
     * Hiển thị tin nhắn của người dùng
     * @param {string} text - Nội dung tin nhắn
     * @param {number} timestamp - (Tùy chọn) Timestamp (giây) để hiển thị
     * @param {boolean} autoScroll - whether to auto-scroll to bottom, default true
     */
    function showUserMessage(text, timestamp = null, autoScroll = true) {
        const userMessageWrapper = $('<div>').addClass('user-message-wrapper');
        const userAvatarIcon = $('<i>').addClass('fa-solid fa-user ml-2');
        const userMessageContent = $('<div>').addClass('user-message');
        const formattedText = text.replace(/\n/g, '<br>').replace(/(<br>\s*)+/g, '<br>');
        const userParagraph = $('<p>').html(formattedText);
        // Thêm nội dung chính
        userMessageContent.append(userParagraph);
        // Dùng timestamp được cung cấp, hoặc lấy time hiện tại nếu là null
        const formattedTime = formatTimestamp(timestamp || getCurrentTime());
        const userTimestamp = $('<div>').addClass('timestamp').text(formattedTime);
        userMessageContent.append(userTimestamp);
        userMessageWrapper.append(userMessageContent).append(userAvatarIcon);
        appendMessage(userMessageWrapper, autoScroll);
    }
    /**
     * Hiển thị tin nhắn của bot
     * @param {string} text - Nội dung tin nhắn
     * @param {Array} fileinfos - (Tùy chọn) Danh sách file đính kèm
     * @param {Array} webinfos - (Tùy chọn) Danh sách kết quả web search
     * @param {number} timestamp - (Tùy chọn) Timestamp (giây) để hiển thị
     * @param {boolean} autoScroll - whether to auto-scroll to bottom, default true
     */
    function showBotMessage(text, fileinfos = null, webinfos = null, timestamp = null, autoScroll = true) {
        const botMessageWrapper = $('<div>').addClass('bot-message-wrapper');
        const botAvatarIcon = $('<i>').addClass('fa-solid fa-robot mr-2');
        const botMessageContent = $('<div>').addClass('bot-message');
        const botParagraph = $('<p>').html(text);
        // Thêm nội dung chính
        botMessageContent.append(botParagraph);
        // Xử lý file đính kèm nếu có (sử dụng thẻ ul/li để liệt kê từng file)
        if (fileinfos && fileinfos.length > 0) {
            const label = $('<h6>')
                .addClass('mt-2')
                .text('Tài liệu tham khảo:');
            const attachments = $('<ul>');

            const filesByName = new Map();
            fileinfos.forEach(fileinfo => {
                if (!filesByName.has(fileinfo.filename)) {
                    filesByName.set(fileinfo.filename, []);
                }
                filesByName.get(fileinfo.filename).push(fileinfo);
            });

            filesByName.forEach((pages, filename) => {
                pages.sort((firstPage, secondPage) =>
                    Number(firstPage.pagenumber) - Number(secondPage.pagenumber)
                );
                const pageNumbers = pages.map(page => page.pagenumber).join(', ');
                const fileinfo = pages[0];
                const fileLink = $('<a>')
                    .attr('href', fileinfo.fileurl)
                    .attr('target', '_blank')
                    .text(filename);
                const listItem = $('<li>')
                    .addClass('attachment-item')
                    .text(`Trang ${pageNumbers} - File `)
                    .append(fileLink);
                attachments.append(listItem);
            });
            botMessageContent.append(label);
            botMessageContent.append(attachments);
        }
        // Xử lý kết quả web search nếu có
        if (webinfos && webinfos.length > 0) {
            const label = $('<h6>')
                .addClass('mt-2')
                .text('Kết quả tìm kiếm web:');
            const webResults = $('<ul>');
            webinfos.forEach(webinfo => {
                const webLink = $('<a>')
                    .attr('href', webinfo.url)
                    .attr('target', '_blank')
                    .text(webinfo.title);
                const listItem = $('<li>')
                    .addClass('attachment-item')
                    .append(webLink);
                webResults.append(listItem);
            });
            botMessageContent.append(label);
            botMessageContent.append(webResults);
        }

        // Dùng timestamp được cung cấp, hoặc lấy time hiện tại nếu là null
        const formattedTime = formatTimestamp(timestamp || getCurrentTime());
        const botTimestamp = $('<div>').addClass('timestamp').text(formattedTime);

        botMessageContent.append(botTimestamp);
        botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
        appendMessage(botMessageWrapper, autoScroll);
    }
    /**
     * Tải tất cả tiêu đề cuộc trò chuyện
     */
    function loadConversationTitles() {
        ajax.call([{
            methodname: 'local_mychatbot_get_conversation_titles',
            args: {},
            done: function(titles) {
                // Xóa danh sách tiêu đề cũ
                sidebarContent.empty();
                if (titles.length === 0) {
                    NoConversation = true;
                }
                else {
                    NoConversation = false;
                    // Thêm từng tiêu đề vào sidebar
                    titles.forEach(function(conv) {
                        addConversationTitleToSidebar(conv.id, conv.title, false);
                    });
                }
            },
            fail: function(ex) {
                notification.exception(ex);
                showSystemMessage(`Lỗi tải danh sách tiêu đề hội thoại: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Thêm một tiêu đề vào sidebar
     * @param {number} id - ID của cuộc trò chuyện
     * @param {string} title - Tiêu đề
     * @param {boolean} prepend - Thêm vào đầu (true) hay cuối (false)
     */
    function addConversationTitleToSidebar(id, title, prepend = false) {
        const item = $('<button>')
            .addClass('btn btn-light sidebar-item')
            .attr('data-id', id)
            .text(title);

        item.on('click', function() {
            onConversationClick(id, $(this));
        });

        if (prepend) {
            sidebarContent.prepend(item);
        } else {
            sidebarContent.append(item);
        }
    }

    /**
     * Xử lý khi click vào một tiêu đề
     * @param {number} id - ID của cuộc trò chuyện
     * @param {any} element - Nút đã được click
     */
    function onConversationClick(id, element) {
        // Đặt lại ID hiện tại
        currentConversationId = id;

        // Xóa cửa sổ chat
        chatWindow.empty();

        // Đánh dấu "active"
        sidebarContent.find('.sidebar-item').removeClass('active');
        element.addClass('active');

        // Hiển thị loading
        showSystemMessage("Đang tải nội dung...", "info");
        chatbotContainer.removeClass('no-before no-after');

        // Gọi API lấy lịch sử chat
        ajax.call([{
            methodname: 'local_mychatbot_get_conversation_history',
            args: { conversationid: id },
            done: function(messages) {
                // Xóa tin nhắn "Đang tải nội dung..."
                chatWindow.empty();
                if (messages.length === 0) {
                    showSystemMessage("Đoạn chat chưa có nội dung.", "info");
                    chatbotContainer.addClass('no-before no-after');
                    return;
                }
                // Đoạn chat đã có nội dung
                // Lặp qua và hiển thị lại các tin nhắn
                messages.forEach(function(msg) {
                    // Tái tạo tin nhắn người dùng
                    showUserMessage(msg.usermessage, msg.timecreated, false);
                    // Tái tạo tin nhắn bot
                    showBotMessage(
                        msg.botresponse, msg.fileinfos, msg.websearchinfos, msg.timecreated, false
                    );
                });
                // Cuộn xuống dưới cùng sau khi tải xong toàn bộ tin nhắn
                chatWindow.animate({
                    scrollTop: chatWindow.prop("scrollHeight")
                }, 400);
                // Ẩn pseudo-elements
                chatbotContainer.addClass('no-before no-after');
            },
            fail: function(ex) {
                notification.exception(ex);
                showSystemMessage(`Lỗi tải lịch sử hội thoại: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Toggle chat actions menu
     */
    function toggleChatActionsMenu() {
        if (chatActionsMenu && chatActionsMenu.length) {
            chatActionsMenu.toggleClass('d-none');
        }
    }
    /**
     * Cập nhật giao diện nút Thêm/Xóa
     * @param {jQuery} btn - Đối tượng nút jQuery
     * @param {string} action - hành động hiện tại ('add', 'delete' hoặc 'replace')
     */
    function updateSuggestionButtonUI(btn, action) {
        if (action === "delete") {
            if (btn.hasClass('btn-add-calendar')) {
                btn.removeClass('btn-add-calendar').addClass('btn-delete-calendar');
                btn.text('🗑️ Xóa khỏi lịch');
                btn.data('action', 'delete');
            } else if (btn.hasClass('btn-replace-calendar')) {
                btn.removeClass('btn-replace-calendar').addClass('btn-delete-calendar');
                btn.text('🗑️ Xóa khỏi lịch');
                btn.data('action', 'delete');
            } else if (btn.hasClass('btn-delete-calendar')) {
                // Đã là nút xóa rồi, không cần thay đổi
            } else {
                btn.addClass('btn-delete-calendar');
                btn.text('🗑️ Xóa khỏi lịch');
                btn.data('action', 'delete');
            }
        } else if (action === "add") {
            btn.removeClass('btn-delete-calendar').addClass('btn-add-calendar');
            btn.text('📅 Thêm vào lịch');
            btn.data('action', 'add');
        } else if (action === "replace") {
            btn.addClass('btn-replace-calendar');
            btn.text('📅 Thay thế lịch cũ');
            btn.data('action', 'replace');
        }

        btn.prop('disabled', false);
    }
    /**
     * Hiển thị thẻ gợi ý làm Quiz
     * @param {string} title - tiêu đề của nhóm gợi ý
     * @param {Array} suggestions - danh sách gợi ý quiz
     * @param {number} timestamp - timestamp của nhắc nhở quiz
     */
    function showQuizSuggestion(title, suggestions, timestamp = null) {
        const botMessageWrapper = $('<div>').addClass('bot-message-wrapper');
        const botAvatarIcon = $('<i>').addClass('fa-solid fa-robot mr-2');
        const botMessageContent = $('<div>').addClass('bot-message');

        botMessageContent.html(`<div class="quiz-suggestion-title">${title}</div>`);

        for (let i = 0; i < suggestions.length; i++) {
            let suggestion = suggestions[i];

            // Format thời gian (Sử dụng hàm formatTimestamp có sẵn)
            let timeString = formatTimestamp(suggestion.suggestedtime);

            // Tạo HTML cho thẻ
            let card = $('<div>').addClass('quiz-suggestion-card');
            // Xác định trạng thái nút dựa trên 'accepted'
            let action = "add"; // Mặc định là thêm
            if (suggestion.accepted === 1) {
                action = "delete"; // Đã thêm rồi, bây giờ là xóa
            } else if (suggestion.exists) {
                action = "replace"; // Đã có sự kiện khác, bây giờ là thay thế
            }
            let cardContent = `
                <span class="suggestion-content">
                    - Thực hiện ${suggestion.quizname} vào lúc
                    <span class="suggestion-time">${timeString}.</span>
                </span>
                <button class="action-calendar-btn" data-id="${suggestion.id}">
                </button>`;
            card.html(cardContent);
            const btn = card.find('.action-calendar-btn');

            // Khởi tạo nút
            updateSuggestionButtonUI(btn, action);

            // Xử lý sự kiện click chung
            btn.on('click', function() {
                let clickedBtn = $(this);
                let action = clickedBtn.data('action');
                let suggestionId = clickedBtn.data('id');

                // Disable nút để tránh click đúp
                clickedBtn.prop('disabled', true).text('⏳ Đang thêm...');

                // gọi API để thêm hoặc xóa sự kiện vào lịch
                if (action === 'add') {
                    ajax.call([{
                        methodname: 'local_mychatbot_add_calendar_quiz_event',
                        args: { suggestionid: suggestionId },
                        done: function(response) {
                            if (response.status === 'success') {
                                notification.addNotification({
                                    message: response.message,
                                    type: 'success'
                                });
                                updateSuggestionButtonUI(clickedBtn, "delete"); // chuyển sang nút xóa
                            } else {
                                notification.addNotification({
                                    message: response.message,
                                    type: 'warning'
                                });
                                // Trường hợp warning (đã thêm rồi)
                                updateSuggestionButtonUI(clickedBtn, "delete"); // Cũng coi như đã thêm
                            }
                        },
                        fail: function(ex) {
                            // Thất bại: reset lại về nút thêm
                            notification.exception(ex);
                            updateSuggestionButtonUI(clickedBtn, "add");
                        }
                    }]);
                } else if (action === 'delete') {
                    ajax.call([{
                        methodname: 'local_mychatbot_delete_calendar_quiz_event',
                        args: { suggestionid: suggestionId },
                        done: function(response) {
                            if (response.status === 'success') {
                                notification.addNotification({
                                    message: response.message,
                                    type: 'success'
                                });
                                updateSuggestionButtonUI(clickedBtn, "add"); // chuyển sang nút thêm
                            } else {
                                notification.addNotification({
                                    message: response.message,
                                    type: 'warning'
                                });
                                updateSuggestionButtonUI(clickedBtn, "add");
                            }
                        },
                        fail: function(ex) {
                            // Thất bại: reset lại về nút xóa
                            notification.exception(ex);
                            updateSuggestionButtonUI(clickedBtn, "delete");
                        }
                    }]);
                } else if (action === 'replace') {
                    ajax.call([{
                        methodname: 'local_mychatbot_replace_calendar_quiz_event',
                        args: { suggestionid: suggestionId },
                        done: function(response) {
                            if (response.status === 'success') {
                                notification.addNotification({
                                    message: response.message,
                                    type: 'success'
                                });
                                updateSuggestionButtonUI(clickedBtn, "delete"); // chuyển sang nút xóa
                            } else {
                                notification.addNotification({
                                    message: response.message,
                                    type: 'warning'
                                });
                                // Trường hợp warning (đã thay thế rồi)
                                updateSuggestionButtonUI(clickedBtn, "delete");
                            }
                        },
                        fail: function(ex) {
                            // Thất bại: reset lại về nút thay thế
                            notification.exception(ex);
                            updateSuggestionButtonUI(clickedBtn, "replace");
                        }
                    }]);
                }
            });
            botMessageContent.append(card);
        }
        const formattedTime = formatTimestamp(timestamp || getCurrentTime());
        const botTimestamp = $('<div>').addClass('timestamp').text(formattedTime);

        botMessageContent.append(botTimestamp);
        botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
        appendMessage(botMessageWrapper, true);
    }
    /**
     * Hiển thị nhắc nhở quiz
     * @param {string} text - Nội dung
     * @param {Array} formatted_quizzes - Danh sách quiz đã định dạng
     * @param {number} timestamp - (Tùy chọn) Timestamp (giây) để hiển thị
     */
    function showQuizReminder(text, formatted_quizzes, timestamp = null) {
        const botMessageWrapper = $('<div>').addClass('bot-message-wrapper');
        const botAvatarIcon = $('<i>').addClass('fa-solid fa-robot mr-2');
        const botMessageContent = $('<div>').addClass('bot-message');
        const lines = text.split('\n');
        // loại bỏ các phần tử rỗng ''
        const filteredLines = lines.filter(line => line.trim() !== '');
        let finalHtml = '';

        for (let i = 0; i < filteredLines.length; i++) {
            let currentLine = filteredLines[i];
            finalHtml += `<div class="reminder-normal-text">${currentLine}</div>`;
            if (i === 0) {
                for (let j = 0; j < formatted_quizzes.length; j++) {
                    let quiz = formatted_quizzes[j];
                    let link = `${M.cfg.wwwroot}/mod/quiz/view.php?id=${quiz.course_module_id}`;
                    let processedLink = `<a href="${link}" target="_blank" rel="noopener noreferrer">(&#9656;)</a>`;
                    let quiz_link = `<span class="reminder-item-link">${processedLink}</span>`;
                    if (quiz.severity_level == 1) {
                        finalHtml += `<div class="reminder-item prio-red">${quiz.content} ${quiz_link}</div>`;
                    }
                    else if (quiz.severity_level == 0) {
                        finalHtml += `<div class="reminder-item prio-orange">${quiz.content} ${quiz_link}</div>`;
                    }
                    else {
                        finalHtml += `<div class="reminder-item">${quiz.content} ${quiz_link}</div>`;
                    }
                }
            }
        }

        botMessageContent.html(finalHtml);

        const formattedTime = formatTimestamp(timestamp || getCurrentTime());
        const botTimestamp = $('<div>').addClass('timestamp').text(formattedTime);

        botMessageContent.append(botTimestamp);
        botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
        appendMessage(botMessageWrapper, true);
    }
    /**
     * Hiển thị nhắc nhở assignment
     * @param {string} text - Nội dung
     * @param {Array} allowed - Danh sách assignment đã định dạng (đã mở submission)
     * @param {Array} not_allowed_yet - Danh sách assignment đã định dạng (chưa mở submission)
     * @param {number} timestamp - (Tùy chọn) Timestamp (giây) để hiển thị
     */
    function showAssignmentReminder(text, allowed, not_allowed_yet, timestamp = null) {
        const botMessageWrapper = $('<div>').addClass('bot-message-wrapper');
        const botAvatarIcon = $('<i>').addClass('fa-solid fa-robot mr-2');
        const botMessageContent = $('<div>').addClass('bot-message');

        const lines = text.split('\n');
        // loại bỏ các phần tử rỗng ''
        const filteredLines = lines.filter(line => line.trim() !== '');
        var finalHtml = '';

        for (let i = 0; i < filteredLines.length; i++) {
            let currentLine = filteredLines[i];
            finalHtml += `<div class="reminder-normal-text">${currentLine}</div>`;
            if (i === 0) {
                if (allowed.length > 0 && not_allowed_yet.length > 0) {
                    for (let j = 0; j < allowed.length; j++) {
                        let assign = allowed[j];
                        let link = `${M.cfg.wwwroot}/mod/assign/view.php?id=${assign.course_module_id}`;
                        let processedLink = `<a href="${link}" target="_blank" rel="noopener noreferrer">(&#9656;)</a>`;
                        let assign_link = `<span class="reminder-item-link">${processedLink}</span>`;
                        if (assign.severity_level == 1) {
                            finalHtml += `<div class="reminder-item prio-red">${assign.content} ${assign_link}</div>`;
                        }
                        else if (assign.severity_level == 0) {
                            finalHtml += `<div class="reminder-item prio-orange">${assign.content} ${assign_link}</div>`;
                        }
                        else {
                            finalHtml += `<div class="reminder-item">${assign.content} ${assign_link}</div>`;
                        }
                    }
                    i = 1;
                    let nextLine = filteredLines[i];
                    finalHtml += `<div class="reminder-normal-text">${nextLine}</div>`;
                    for (let j = 0; j < not_allowed_yet.length; j++) {
                        let assign = not_allowed_yet[j];
                        let link = `${M.cfg.wwwroot}/mod/assign/view.php?id=${assign.course_module_id}`;
                        let processedLink = `<a href="${link}" target="_blank" rel="noopener noreferrer">(&#9656;)</a>`;
                        let assign_link = `<span class="reminder-item-link">${processedLink}</span>`;
                        if (assign.severity_level == 1) {
                            finalHtml += `<div class="reminder-item prio-red">${assign.content} ${assign_link}</div>`;
                        }
                        else if (assign.severity_level == 0) {
                            finalHtml += `<div class="reminder-item prio-orange">${assign.content} ${assign_link}</div>`;
                        }
                        else {
                            finalHtml += `<div class="reminder-item">${assign.content} ${assign_link}</div>`;
                        }
                    }
                }
                else if (allowed.length > 0) {
                    for (let j = 0; j < allowed.length; j++) {
                        let assign = allowed[j];
                        let link = `${M.cfg.wwwroot}/mod/assign/view.php?id=${assign.course_module_id}`;
                        let processedLink = `<a href="${link}" target="_blank" rel="noopener noreferrer">(&#9656;)</a>`;
                        let assign_link = `<span class="reminder-item-link">${processedLink}</span>`;
                        if (assign.severity_level == 1) {
                            finalHtml += `<div class="reminder-item prio-red">${assign.content} ${assign_link}</div>`;
                        }
                        else if (assign.severity_level == 0) {
                            finalHtml += `<div class="reminder-item prio-orange">${assign.content} ${assign_link}</div>`;
                        }
                        else {
                            finalHtml += `<div class="reminder-item">${assign.content} ${assign_link}</div>`;
                        }
                    }
                }
                else if (not_allowed_yet.length > 0) {
                    for (let j = 0; j < not_allowed_yet.length; j++) {
                        let assign = not_allowed_yet[j];
                        let link = `${M.cfg.wwwroot}/mod/assign/view.php?id=${assign.course_module_id}`;
                        let processedLink = `<a href="${link}" target="_blank" rel="noopener noreferrer">(&#9656;)</a>`;
                        let assign_link = `<span class="reminder-item-link">${processedLink}</span>`;
                        if (assign.severity_level == 1) {
                            finalHtml += `<div class="reminder-item prio-red">${assign.content} ${assign_link}</div>`;
                        }
                        else if (assign.severity_level == 0) {
                            finalHtml += `<div class="reminder-item prio-orange">${assign.content} ${assign_link}</div>`;
                        }
                        else {
                            finalHtml += `<div class="reminder-item">${assign.content} ${assign_link}</div>`;
                        }
                    }
                }
            }
        }

        botMessageContent.html(finalHtml);

        const formattedTime = formatTimestamp(timestamp || getCurrentTime());
        const botTimestamp = $('<div>').addClass('timestamp').text(formattedTime);

        botMessageContent.append(botTimestamp);
        botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
        appendMessage(botMessageWrapper, true);
    }
    /**
     * check status Chatbot
     */
    function checkChatbotStatus() {
        if (isCheckingStatus) {
            return;
        }
        isCheckingStatus = true;
        // Xóa các tin nhắn trạng thái cũ
        chatWindow.find(
            '.system-message.status-ok, .system-message.status-error, .system-message.info'
        ).remove();
        showSystemMessage("Kiểm tra trạng thái chatbot...", "info");

        ajax.call([{
            methodname: 'local_mychatbot_check_status',
            args: {},
            done: function(data) {
                chatWindow.find('.system-message.info').filter(function() {
                    return $(this).text().includes("Kiểm tra trạng thái chatbot...");
                }).remove();

                if (data && data.status === 'ok') {
                    showSystemMessage(data.message, "status-ok");

                    showWelcomeMessage(data.user_fullname);
                    // Tải danh sách tiêu đề cuộc trò chuyện
                    loadConversationTitles();
                }
                else {
                    showSystemMessage(data.message || 'Máy chủ Chatbot đang gặp vấn đề.', "status-error");
                }
            },
            fail: function(ex) {
                chatWindow.find('.system-message.info').filter(function() {
                    return $(this).text().includes("Kiểm tra trạng thái chatbot...");
                }).remove();
                notification.exception(ex);
                showSystemMessage(`Lỗi khi kiểm tra trạng thái chatbot: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * check whether there are new reminders and add notification badge to chat actions menu
     */
    function checkNewReminders() {
        ajax.call([{
            methodname: 'local_mychatbot_check_new_reminders',
            args: {},
            done: function(data) {
                let num_all = 0;
                // Kiểm tra và thêm badge thông báo nếu có nhắc nhở mới cho quiz
                if (data && data.quiz && data.quiz !== 0) {
                    num_all = num_all + data.quiz;
                    $('#quiz-badge').text(data.quiz).removeClass('d-none');
                }
                // Kiểm tra và thêm badge thông báo nếu có nhắc nhở mới cho assignment
                if (data && data.assignment && data.assignment !== 0) {
                    num_all = num_all + data.assignment;
                    $('#assignment-badge').text(data.assignment).removeClass('d-none');
                }
                if (num_all !== 0) {
                    $('#general-badge').text(num_all).removeClass('d-none');
                }
            },
            fail: function(ex) {
                notification.exception(ex);
                showSystemMessage(`Lỗi khi kiểm tra nhắc nhở mới: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * hide/show chatbox
     */
    function toggleChatbot() {
        if (!chatbotContainer || !chatbotContainer.length) {
            return;
        }
        let isHidden = chatbotContainer.hasClass('d-none');
        if (isHidden) {
            checkNewReminders();
        }
        chatbotContainer.toggleClass('d-none');
        if (isHidden) {
            if (isCheckingStatus === false) {
                checkChatbotStatus();
            }
            // Focus vào ô nhập liệu
            if (chatInput && chatInput.length) {
                setTimeout(function() {
                    autoGrowTextarea(chatInput[0], true);
                    chatInput.focus();
                }, 0);
            }
            // Update scroll and focus even if status is not checked
            if (chatWindow && chatWindow.length) {
                chatWindow.scrollTop(chatWindow.prop("scrollHeight"));
            }
        }
    }
    /**
     * adjust the height of the textarea based on its content.
     * @param {Object} textareaElement - Dom element of the textarea
     * @param {Boolean} forceSingleLine - if true, co textarea to 1 row.
     */
    function autoGrowTextarea(textareaElement, forceSingleLine = false) {
        if (!textareaElement) {
            return;
        }
        const textarea = $(textareaElement);
        const minHeight = parseInt(textarea.css('min-height'), 10);
        const maxHeight = parseInt(textarea.css('max-height'), 10);
        if (forceSingleLine) {
            textarea.height(minHeight);
            textarea.css('overflow-y', 'hidden');
            textarea.removeClass('has-scrollbar');
            return;
        }
        textarea.height('auto');
        let scrollHeight = textareaElement.scrollHeight;
        if (scrollHeight <= minHeight) {
            textarea.height(minHeight);
            textarea.css('overflow-y', 'hidden');
            textarea.removeClass('has-scrollbar');
        }
        else if (scrollHeight <= maxHeight) {
            textarea.height(scrollHeight);
            textarea.css('overflow-y', 'hidden');
            textarea.removeClass('has-scrollbar');
        }
        else {
            textarea.height(maxHeight);
            textarea.css('overflow-y', 'auto');
            textarea.addClass('has-scrollbar');
        }
    }
    /**
     * Send message to backend via AJAX
     */
    function sendMessage() {
        if (inputMode == 'quiz') {
            if (!validateQuizRequestData()) {
                return;
            }
            processQuizGenerationRequest();
            return; // Dừng hàm tại đây, không chạy xuống phần chat bình thường
        }

        let message = chatInput.val().trim();
        if (!message) {
            showChatInputError();
            if (chatInput.is('textarea')) {
                autoGrowTextarea(chatInput[0], true);
            }
            return;
        }
        // Lấy timestamp 1 LẦN số nguyên unix timestamp (giây)
        const messageTime = getCurrentTime();
        // Hiển thị tin nhắn người dùng ngay lập tức
        showUserMessage(message, messageTime, true);
        // Hiệu ứng Chatbot đang xử lý yêu cầu
        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa-solid fa-robot text-primary"></i>
            </div>    
        `);
        appendMessage(loadingEffect, true);

        chatInput.val('');
        if (chatInput.is('textarea')) {
            autoGrowTextarea(chatInput[0], true);
        }

        // Gọi Web Service
        ajax.call([{
            methodname: 'local_mychatbot_send_message',
            args: {
                message: message,
                conversationid: currentConversationId,
                timecreated: messageTime // Gửi số nguyên thời gian lên server
            },
            done: function(data) {
                // Xóa hiệu ứng loading
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                // Dùng lại timestamp cũ cho tin nhắn của bot
                showBotMessage(data.response, data.fileinfos, data.websearchinfos, messageTime, true);
                if (data.newconversation.id !== -1) {
                    var newConv = data.newconversation;
                    // 1. Cập nhật ID hiện tại
                    currentConversationId = newConv.id;
                    // 2. Thêm tiêu đề mới vào sidebar
                    // true = thêm vào đầu
                    addConversationTitleToSidebar(newConv.id, newConv.title, true);
                    // 3. Đánh dấu tiêu đề đó là "active"
                    sidebarContent.find('.sidebar-item').removeClass('active');
                    sidebarContent.find('.sidebar-item[data-id="' + newConv.id + '"]').addClass('active');
                    // 4. Xử lý logic cho sidebar-empty và sidebar-content
                    if (NoConversation) {
                        // Đây là cuộc hội thoại đầu tiên
                        NoConversation = false;
                        // Nếu sidebar đang mở thì cần cập nhật d-none cho sidbar-empty và sidebar-content ngay
                        if (chatbotContainer.hasClass('sidebar-expanded')) {
                            sidebarEmpty.addClass('d-none');
                            sidebarContent.removeClass('d-none');
                        }
                    } else {
                        // Không phải cuộc hội thoại đầu tiên, không cần xử lý gì thêm
                    }
                }
            },
            fail: function(ex) {
                // Xóa hiệu ứng loading
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi khi gửi tin nhắn: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Hiển thị tài liệu đề xuất cho quiz
     * @param {Array} data - Dữ liệu tài liệu
     */
    function showDocNeededForQuiz(data) {
        if (data && data.length > 0) {
            for (let i = 0; i < data.length; i++) {
                let item = data[i];
                showBotMessage(item.content, item.fileinfos, item.websearchinfos, item.timecreated, true);
            }
        }
    }
    /**
     * Gọi API lấy tài liệu cần cho quiz
     */
    function fetchDocNeededForQuiz() {
        // Hiệu ứng loading
        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa fa-robot"></i>
            </div>    
        `);
        appendMessage(loadingEffect, true);

        ajax.call([{
            methodname: 'local_mychatbot_get_doc_needed_for_quiz',
            args: {},
            done: function(data) {
                // Xóa hiệu ứng loading
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                if (data && data.old && data.new && (data.old.length > 0 || data.new.length > 0)) {
                    chatWindow.append(
                        $('<div>').addClass('chat-separator pill').text('TÀI LIỆU ĐỀ XUẤT')
                    );
                    if (data.old.length > 0) {
                        showDocNeededForQuiz(data.old);
                        if (data.new.length > 0) {
                            chatWindow.append(
                                $('<div>').addClass('chat-separator pill').text('--- MỚI NHẤT ---')
                            );
                            showDocNeededForQuiz(data.new);
                        }
                    } else {
                        showDocNeededForQuiz(data.new);
                    }
                }
            },
            fail: function(ex) {
                // Xóa hiệu ứng loading
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi khi lấy gợi ý tài liệu cần cho quiz: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Gọi API lấy danh sách suggestion hiện tại
     */
    function fetchQuizSuggestions() {
        // Hiệu ứng loading
        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa fa-robot"></i>
            </div>    
        `);
        appendMessage(loadingEffect, true);
        ajax.call([{
            methodname: 'local_mychatbot_get_current_quiz_suggestions',
            args: {},
            done: function(data) {
                // Xóa hiệu ứng loading
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                if (data && data.title && data.suggestions && data.suggestions.length > 0) {
                    chatWindow.append(
                        $('<div>').addClass('chat-separator pill').text('THỜI GIAN ĐỀ XUẤT')
                    );
                    showQuizSuggestion(
                        data.title,
                        data.suggestions,
                        data.timecreated
                    );
                }
                fetchDocNeededForQuiz();
            },
            fail: function(ex) {
                // Xóa hiệu ứng loading
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi khi lấy gợi ý quiz: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Xử lý click nút Nhắc nhở quiz
     */
    function handleQuizReminderClick() {
        // Dọn dẹp chat window
        chatWindow.empty();
        // Ẩn badge thông báo nếu đang hiện
        let quiz_badge_num = parseInt($('#quiz-badge').text());
        let general_badge_num = parseInt($('#general-badge').text());
        if (!isNaN(quiz_badge_num) && !isNaN(general_badge_num)) {
            let new_general_badge_num = general_badge_num - quiz_badge_num;
            if (new_general_badge_num <= 0) {
                $('#general-badge').text('').addClass('d-none');
            } else {
                $('#general-badge').text(new_general_badge_num);
            }
        }
        $('#quiz-badge').text('').addClass('d-none');
         // Đặt về trạng thái "không hội thoại"
        currentConversationId = 0;
        sidebarContent.find('.sidebar-item').removeClass('active');
        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa fa-robot"></i>
            </div>    
        `);
        appendMessage(loadingEffect, true);

        // Gọi API (hàm này đã bao gồm logic cooldown)
        ajax.call([{
            methodname: 'local_mychatbot_get_quiz_reminder_history',
            args: {},
            done: function(reminder) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                if (reminder && reminder.response && reminder.response.trim() !== '') {
                    if (reminder.formatted_quizzes.length > 0) {
                        chatWindow.append(
                            $('<div>').addClass('chat-separator pill').text('NHẮC NHỞ MỚI NHẤT')
                        );
                        showQuizReminder(
                            reminder.response,
                            reminder.formatted_quizzes,
                            reminder.timecreated
                        );
                        fetchQuizSuggestions();
                    }
                    else {
                        let declineMsgContainer = $('<div>')
                            .addClass('d-flex flex-column mt-5');
                        let icon = $('<i>')
                            .addClass('fa-solid fa-heart-crack align-self-center')
                            .css('font-size', '3rem');
                        let declineMsg = $('<p>')
                            .addClass('decline-message')
                            .text(reminder.response);

                        declineMsgContainer.append(icon).append(declineMsg);
                        chatWindow.append(declineMsgContainer);
                    }
                }
            },
            fail: function(ex) {
                chatWindow.empty();
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi khi lấy nhắc nhở quiz: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Xử lý click nút Nhắc nhở assignment
     */
    function handleAssignmentReminderClick() {
        // Dọn dẹp chat window
        chatWindow.empty();
        // Ẩn badge thông báo nếu đang hiện
        let assignment_badge_num = parseInt($('#assignment-badge').text());
        let general_badge_num = parseInt($('#general-badge').text());
        if (!isNaN(assignment_badge_num) && !isNaN(general_badge_num)) {
            let new_general_badge_num = general_badge_num - assignment_badge_num;
            if (new_general_badge_num <= 0) {
                $('#general-badge').text('').addClass('d-none');
            } else {
                $('#general-badge').text(new_general_badge_num);
            }
        }
        $('#assignment-badge').text('').addClass('d-none');
         // Đặt về trạng thái "không hội thoại"
        currentConversationId = 0;
        sidebarContent.find('.sidebar-item').removeClass('active');
        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa fa-robot"></i>
            </div>    
        `);
        appendMessage(loadingEffect, true);

        // Gọi API
        ajax.call([{
            methodname: 'local_mychatbot_get_assignment_reminder_history',
            args: {},
            done: function(reminder) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');

                if (reminder && reminder.response && reminder.response.trim() !== '') {
                    if (
                        reminder.allowed_submission_assignments.length > 0 ||
                        reminder.not_allowed_submission_assignments.length > 0
                    ) {
                        chatWindow.append(
                            $('<div>').addClass('chat-separator pill').text('NHẮC NHỞ MỚI NHẤT')
                        );
                        showAssignmentReminder(
                            reminder.response,
                            reminder.allowed_submission_assignments,
                            reminder.not_allowed_submission_assignments,
                            reminder.timecreated
                        );
                    }
                    else {
                        // reminder.response là thông báo cần hiển thị
                        let declineMsgContainer = $('<div>')
                            .addClass('d-flex flex-column mt-5');
                        let icon = $('<i>')
                            .addClass('fa-solid fa-heart-crack align-self-center')
                            .css('font-size', '3rem');
                        let declineMsg = $('<p>')
                            .addClass('decline-message')
                            .text(reminder.response);

                        declineMsgContainer.append(icon).append(declineMsg);
                        chatWindow.append(declineMsgContainer);
                    }
                }
            },
            fail: function(ex) {
                chatWindow.empty();
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi khi lấy nhắc nhở assignment: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Xử lý khi bắt đầu cuộc trò chuyện mới
     */
    function handleNewChat() {
        // Đặt lại ID cuộc trò chuyện
        currentConversationId = 0;
        // Xóa cửa sổ chat
        if (chatWindow && chatWindow.length) {
            chatWindow.empty();
        }
        // Xóa active
        sidebarContent.find('.sidebar-item').removeClass('active');
        // Đặt lại cờ kiểm tra trạng thái
        isCheckingStatus = false;
        // Chạy lại checkChatbotStatus
        checkChatbotStatus();
    }
    /**
     * Xử lý click nút Kiểm tra tiến độ khóa học
     */
    function handleCourseProgressClick() {
        // Dọn dẹp chat window và reset state
        chatWindow.empty();
        currentConversationId = 0;
        sidebarContent.find('.sidebar-item').removeClass('active');

        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa fa-robot"></i>
            </div>
        `);
        appendMessage(loadingEffect, true);

        let urlParams = new URLSearchParams(window.location.search);
        let courseId = parseInt(urlParams.get('id'));

        // Nếu đang ở trong một khóa học rồi (có id trong URL) thì ưu tiên lấy id đó,
        // không thì mới gọi API lấy danh sách khóa học giảng dạy
        if (courseId && !isNaN(courseId)) {
            // Gọi API để phân tích dữ liệu khóa học này (truy vấn DB Moodle -> gọi FastAPI)
            ajax.call([{
                methodname: 'local_mychatbot_analyze_course_progress',
                args: { courseid: courseId },
                done: function(data) {
                    loadingEffect.remove();
                    chatbotContainer.addClass('no-before no-after');
                    if (data && data.response && data.chartdata) {
                        showProgressMessage(data);
                    } else {
                        showSystemMessage("Không nhận được phản hồi phân tích.", "status-error");
                    }
                },
                fail: function(ex) {
                    loadingEffect.remove();
                    chatbotContainer.addClass('no-before no-after');
                    notification.exception(ex);
                    showSystemMessage(`Lỗi phân tích tiến độ: (${ex.message})`, "status-error");
                }
            }]);
        }
        else {
            // Ngược lại, Gọi API lấy danh sách khóa học mà người dùng là giảng viên
            ajax.call([{
                methodname: 'local_mychatbot_get_teacher_courses',
                args: {},
                done: function(data) {
                    loadingEffect.remove();
                    chatbotContainer.addClass('no-before no-after');

                    if (data && data.courses && data.courses.length > 0) {
                        showTeacherCourses(data.courses);
                    }
                    else {
                        let declineMsgContainer = $('<div>')
                            .addClass('d-flex flex-column mt-5');
                        let icon = $('<i>')
                            .addClass('fa-solid fa-face-sad-tear align-self-center')
                            .css('font-size', '3rem');
                        let declineMsg = $('<p>')
                            .addClass('decline-message')
                            .text("Bạn không giảng dạy khóa học nào.");

                        declineMsgContainer.append(icon).append(declineMsg);
                        chatWindow.append(declineMsgContainer);
                    }
                },
                fail: function(ex) {
                    loadingEffect.remove();
                    chatbotContainer.addClass('no-before no-after');
                    notification.exception(ex);
                    showSystemMessage(`Lỗi khi lấy danh sách khóa học: (${ex.message})`, "status-error");
                }
            }]);
        }
    }
    /**
     * Hiển thị danh sách khóa học để người dùng chọn
     * @param {Array} courses - Danh sách khóa học
     */
    function showTeacherCourses(courses) {
        const botMessageWrapper = $('<div>').addClass('bot-message-wrapper');
        const botAvatarIcon = $('<i>').addClass('fa-solid fa-robot mr-2');
        const botMessageContent = $('<div>').addClass('bot-message');

        botMessageContent.html('<p>Chọn một khóa học để xem tiến độ:</p>');

        // Tạo container chứa các nút khóa học
        const courseList = $('<div>').addClass('course-selection-list d-flex flex-column mt-2');

        courses.forEach(function(course) {
            const btn = $('<button>')
                .addClass('btn btn-outline-primary btn-sm m-1 course-select-btn')
                .text(course.fullname)
                .data('courseid', course.id)
                .data('coursename', course.fullname);

            btn.on('click', function() {
                // Vô hiệu hóa tất cả các nút để tránh click đúp
                $('.course-select-btn').prop('disabled', true);

                let cid = $(this).data('courseid');
                let cname = $(this).data('coursename');
                handleCourseSelection(cid, cname);
                $('.course-select-btn').prop('disabled', false);
            });
            courseList.append(btn);
        });

        botMessageContent.append(courseList);

        const formattedTime = formatTimestamp(getCurrentTime());
        botMessageContent.append($('<div>').addClass('timestamp').text(formattedTime));

        botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
        appendMessage(botMessageWrapper, true);
    }
    /**
     * Xử lý khi giảng viên chọn 1 khóa học cụ thể để xem tiến độ
     * @param {number} courseId - ID của khóa học
     * @param {string} courseName - Tên của khóa học
     */
    function handleCourseSelection(courseId, courseName) {
        // Hiển thị tin nhắn như thể người dùng vừa gõ vào
        showUserMessage(`Kiểm tra tiến độ khóa: ${courseName}`, getCurrentTime(), true);

        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa fa-robot"></i>
            </div>
        `);
        appendMessage(loadingEffect, true);

        // Gọi API để phân tích dữ liệu khóa học này (truy vấn DB Moodle -> gọi FastAPI)
        ajax.call([{
            methodname: 'local_mychatbot_analyze_course_progress',
            args: { courseid: courseId },
            done: function(data) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                if (data && data.response && data.chartdata) {
                    showProgressMessage(data);
                } else {
                    showSystemMessage("Không nhận được phản hồi phân tích.", "status-error");
                }
            },
            fail: function(ex) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi phân tích tiến độ: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Xử lý gọi API lấy phân tích chi tiết của 1 học viên
     * @param {number} courseId - ID của khóa học
     * @param {number} userId - ID của học viên
     * @param {string} studentName - Tên của học viên (dùng để hiển thị trong tin nhắn người dùng)
     */
    function handleStudentProgressClick(courseId, userId, studentName) {
        showUserMessage(`Phân tích chi tiết học viên: ${studentName}`, getCurrentTime(), true);

        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa fa-robot"></i>
            </div>
        `);
        appendMessage(loadingEffect, true);

        ajax.call([{
            methodname: 'local_mychatbot_analyze_student_progress',
            args: { courseid: courseId, userid: userId },
            done: function(data) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');

                if (data && data.response) {
                    showBotMessage(data.response, null, null, getCurrentTime(), true);
                }
            },
            fail: function(ex) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi phân tích học viên: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Hiển thị báo cáo tiến độ của bot
     * @param {Object} progress_data - Dữ liệu tiến độ phản hồi từ AI server
     */
    function showProgressMessage(progress_data) {
        const botMessageWrapper = $('<div>').addClass('bot-message-wrapper');
        const botAvatarIcon = $('<i>').addClass('fa-solid fa-robot mr-2');
        const botMessageContent = $('<div>').addClass('bot-message');
        const formattedText = progress_data.response.replace(/\n/g, '<br>').replace(/(<br>\s*)+/g, '<br>');
        const botParagraph = $('<p>').html(formattedText);
        // Thêm nội dung chính
        botMessageContent.append(botParagraph);

        const chartdata = progress_data.chartdata; // Dữ liệu biểu đồ từ server
        // Hiển thị biểu đồ tiến độ dạng cột bằng HTML/CSS
        const chartWrapper = $('<div>').addClass(
            'chart-wrapper d-flex justify-content-center my-2'
        );
        const chartContent = $('<div>').addClass('chart-message');

        const title = $('<h6>').text('Tổng quan khóa học').addClass('mb-3 text-center border-bottom pb-2');
        chartContent.append(title);
        const chartContainer = $('<div>').addClass('progress-chart-container d-flex justify-content-around align-items-end');

        // Hàm helper để tạo 1 cột biểu đồ
        const createColumn = (label, percent, colorClass, tooltipText) => {
            const col = $('<div>').addClass('chart-col d-flex flex-column align-items-center position-relative');
            // Thêm Tooltip nếu có
            if (tooltipText) {
                const tooltip = $('<div>').addClass('chart-tooltip').html(tooltipText);
                col.append(tooltip);
                col.addClass('has-tooltip');
            }

            // Phần thanh hiển thị (Bar)
            const barWrapper = $('<div>').addClass('bar-wrapper');
            const bar = $('<div>').addClass(`bar ${colorClass}`).css('height', `${percent}%`);
            barWrapper.append(bar);

            // Nhãn % và Tên nhóm
            const percentLabel = $('<span>').addClass('font-weight-bold small mb-1').text(`${percent}%`);
            const textLabel = $('<span>').addClass('small text-muted mt-1').text(label);

            col.append(percentLabel).append(barWrapper).append(textLabel);
            return col;
        };

        // Thêm 3 cột: Tốt, Trung bình, Yếu
        if (chartdata.good_percent > 0) {
            chartContainer.append(createColumn('Tốt (>=80%)', chartdata.good_percent, 'bg-success', chartdata.top_names));
        }
        if (chartdata.average_percent > 0) {
            chartContainer.append(
                createColumn('TB (40-79%)', chartdata.average_percent, 'bg-warning', null)
            ); // TB không cần tooltip
        }
        if (chartdata.poor_percent > 0) {
            chartContainer.append(createColumn('Yếu (<40%)', chartdata.poor_percent, 'bg-danger', chartdata.bottom_names));
        }

        chartWrapper.append(chartContent.append(chartContainer));
        botMessageContent.append(chartWrapper);

        // Dùng timestamp được cung cấp, hoặc lấy time hiện tại nếu là null
        const formattedTime = formatTimestamp(getCurrentTime());
        const botTimestamp = $('<div>').addClass('timestamp').text(formattedTime);

        botMessageContent.append(botTimestamp);
        botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
        appendMessage(botMessageWrapper, true);
    }
    /**
     * Hiên thị lại tất cả các yêu cầu tạo quiz đã có trong lịch sử
     * Yêu cầu nào có saved = 0, thì cho phép người dùng chọn câu hỏi và nhấn saveBtn để lưu vào ngân hàng câu hỏi
     * Yêu cầu nào có saved = 1 thì hiển thị dưới dạng đã được lưu (disabled checkbox và nút saveBtn)
     * @param {Array} req_history_data - Dữ liệu lịch sử yêu cầu tạo quiz
     */
    function showQuizGenRequestHistory(req_history_data) {
        for (let i = 0; i < req_history_data.length; i++) {
            let current_req = req_history_data[i];

            showUserMessage(current_req.userrequest, current_req.timecreated, true);

            const botMessageWrapper = $('<div>').addClass('bot-message-wrapper');
            const botAvatarIcon = $('<i>').addClass('fa-solid fa-robot mr-2');
            const botMessageContent = $('<div>').addClass('bot-message');

            let questions = current_req.questions;
            let previewHtml = `
                <h6 class="mb-3 border-bottom pb-2 text-success">
                    <i class="fa fa-check-circle"></i> Bộ ${questions.length} câu hỏi
                </h6>
            `;
            if (current_req.saved == 1) {
                previewHtml += `
                    <p class="small text-muted mb-2">
                        <i class="fa fa-check text-success"></i>
                        Đã lưu vào "${current_req.saved_in_course}" - ${formatTimestamp(current_req.timesaved)}.
                    </p>
                `;
            } else {
                previewHtml += `
                    <p class="small text-muted mb-2">
                        Ở trang khóa học cụ thể, chọn các câu hỏi muốn lưu, nhấn "Lưu" để thêm vào ngân hàng câu hỏi của khóa học đó
                    </p>
                `;
            }
            previewHtml += `<div class="quiz-preview-list" style="max-height: 300px; overflow-y: auto; font-size: 0.85rem;">`;

            // Bây giờ, mỗi question sẽ có thêm độ khó (level) là easy/medium/hard,
            // nên cần lọc nhóm câu hỏi theo độ khó trước khi render
            let easyQuestions = questions.filter(q => q.level === 'easy');
            let mediumQuestions = questions.filter(q => q.level === 'medium');
            let hardQuestions = questions.filter(q => q.level === 'hard');
            // Lặp qua từng câu hỏi để render
            let index = 0; // Biến index dùng chung để đánh số câu hỏi liên tục giữa các độ khó
            // Đầu tiên render câu hỏi dễ, sau đó đến trung bình và khó, nhưng index vẫn tăng liên tục để đánh số câu hỏi
            // Thêm tiêu đề từng độ khó trước khi render câu hỏi của độ khó đó
            if (easyQuestions.length > 0) {
                previewHtml += `<div class="my-2 text-success"><strong>Dễ (Ghi nhớ):</strong></div>`;
                easyQuestions.forEach((q) => {
                    let checkedFlag = 'checked'; // Mặc định checked
                    if (current_req.saved == 1 && q.saved == 0) {
                        checkedFlag = ''; // Nếu yêu cầu đã lưu nhưng câu hỏi này chưa được lưu, thì không checked
                    }
                    previewHtml += `
                        <div class="p-2 mb-2 border rounded bg-white d-flex align-items-start question-preview-item">
                            <input type="checkbox" class="mt-1 mr-2 quiz-question-checkbox" ${checkedFlag} data-index="${index}">
                            <div class="flex-grow-1">
                                <strong>Câu ${index + 1}: ${q.question_text}</strong>
                                <ul class="pl-3 mb-1 mt-1" style="list-style-type: lower-alpha;">
                    `;

                    q.options.forEach((opt, optIndex) => {
                        let isCorrect = (optIndex === q.correct_answer_index);
                        let textStyle = isCorrect ? 'color: green; font-weight: bold;' : '';
                        let checkMark = isCorrect ? ' <i class="fa fa-check text-success"></i>' : '';
                        previewHtml += `<li style="${textStyle}">${opt}${checkMark}</li>`;
                    });

                    previewHtml += `
                                </ul>
                                <div class="text-muted small"><em>Giải thích: ${q.explanation}</em></div>
                            </div>
                        </div>
                    `;
                    index++;
                });
            }
            if (mediumQuestions.length > 0) {
                previewHtml += `<div class="my-2 text-primary"><strong>Trung bình (Thông hiểu):</strong></div>`;
                mediumQuestions.forEach((q) => {
                    let checkedFlag = 'checked'; // Mặc định checked
                    if (current_req.saved == 1 && q.saved == 0) {
                        checkedFlag = ''; // Nếu yêu cầu đã lưu nhưng câu hỏi này chưa được lưu, thì không checked
                    }
                    previewHtml += `
                        <div class="p-2 mb-2 border rounded bg-white d-flex align-items-start question-preview-item">
                            <input type="checkbox" class="mt-1 mr-2 quiz-question-checkbox" ${checkedFlag} data-index="${index}">
                            <div class="flex-grow-1">
                                <strong>Câu ${index + 1}: ${q.question_text}</strong>
                                <ul class="pl-3 mb-1 mt-1" style="list-style-type: lower-alpha;">
                    `;

                    q.options.forEach((opt, optIndex) => {
                        let isCorrect = (optIndex === q.correct_answer_index);
                        let textStyle = isCorrect ? 'color: green; font-weight: bold;' : '';
                        let checkMark = isCorrect ? ' <i class="fa fa-check text-success"></i>' : '';
                        previewHtml += `<li style="${textStyle}">${opt}${checkMark}</li>`;
                    });

                    previewHtml += `
                                </ul>
                                <div class="text-muted small"><em>Giải thích: ${q.explanation}</em></div>
                            </div>
                        </div>
                    `;
                    index++;
                });
            }
            if (hardQuestions.length > 0) {
                previewHtml += `<div class="my-2 text-warning"><strong>Khó (Vận dụng):</strong></div>`;
                hardQuestions.forEach((q) => {
                    let checkedFlag = 'checked'; // Mặc định checked
                    if (current_req.saved == 1 && q.saved == 0) {
                        checkedFlag = ''; // Nếu yêu cầu đã lưu nhưng câu hỏi này chưa được lưu, thì không checked
                    }
                    previewHtml += `
                        <div class="p-2 mb-2 border rounded bg-white d-flex align-items-start question-preview-item">
                            <input type="checkbox" class="mt-1 mr-2 quiz-question-checkbox" ${checkedFlag} data-index="${index}">
                            <div class="flex-grow-1">
                                <strong>Câu ${index + 1}: ${q.question_text}</strong>
                                <ul class="pl-3 mb-1 mt-1" style="list-style-type: lower-alpha;">
                    `;

                    q.options.forEach((opt, optIndex) => {
                        let isCorrect = (optIndex === q.correct_answer_index);
                        let textStyle = isCorrect ? 'color: green; font-weight: bold;' : '';
                        let checkMark = isCorrect ? ' <i class="fa fa-check text-success"></i>' : '';
                        previewHtml += `<li style="${textStyle}">${opt}${checkMark}</li>`;
                    });

                    previewHtml += `
                                </ul>
                                <div class="text-muted small"><em>Giải thích: ${q.explanation}</em></div>
                            </div>
                        </div>
                    `;
                    index++;
                });
            }
            previewHtml += `</div>`;

            // Nút Lưu (kiểm tra current_req.saved)
            if (current_req.saved == 1) {
                // Vì đã lưu, disabled saveBtn và hiện số câu hỏi được lưu
                let text = `Đã chọn ${questions.filter(q => q.saved === 1).length}/${questions.length} câu hỏi`;
                previewHtml += `
                    <button class="btn btn-success btn-sm w-100 mt-2 btn-save-quiz-to-moodle disabled">
                        <i class="fa fa-save"></i> ${text}
                    </button>
                `;
                botMessageContent.html(previewHtml);
                botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
                appendMessage(botMessageWrapper, true);

                // --- Vì đã lưu rồi, disabled tất cả checkbox ---
                let checkboxes = botMessageContent.find('.quiz-question-checkbox');
                checkboxes.prop('disabled', true);
            } else {
                previewHtml += `
                    <button class="btn btn-success btn-sm w-100 mt-2 btn-save-quiz-to-moodle">
                        <i class="fa fa-save"></i> Lưu <span class="selected-count">${questions.length}</span> câu hỏi đã chọn
                    </button>
                `;
                botMessageContent.html(previewHtml);
                botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
                appendMessage(botMessageWrapper, true);
                // --- LOGIC XỬ LÝ CHỌN CÂU HỎI ---
                const saveBtn = botMessageContent.find('.btn-save-quiz-to-moodle');
                const checkboxes = botMessageContent.find('.quiz-question-checkbox');
                const countDisplay = saveBtn.find('.selected-count');

                // Lắng nghe sự kiện thay đổi trên các checkbox
                checkboxes.off('change').on('change', function() {
                    let checkedCount = checkboxes.filter(':checked').length;
                    // Cập nhật số lượng hiển thị trên nút
                    countDisplay.text(checkedCount);
                    // Bật/Tắt nút Lưu: Chỉ cho phép click nếu có ít nhất 1 câu được chọn
                    if (checkedCount > 0) {
                        saveBtn.prop('disabled', false);
                        saveBtn.removeClass('btn-secondary').addClass('btn-success');
                    } else {
                        saveBtn.prop('disabled', true);
                        saveBtn.removeClass('btn-success').addClass('btn-secondary');
                    }
                });

                // Gắn sự kiện click cho nút "Lưu vào ngân hàng câu hỏi"
                saveBtn.off('click').on('click', function() {
                    // Lọc ra danh sách câu hỏi thực sự được chọn
                    let selectedQuestions = [];
                    checkboxes.filter(':checked').each(function() {
                        let index = $(this).data('index');
                        selectedQuestions.push(questions[index]);
                    });
                    executeSaveQuizAction(selectedQuestions, current_req.request_id, saveBtn, checkboxes);
                });
            }
        }
    }
    /**
     * Bật chế độ tạo quiz
     */
    function handleCreateQuizClick() {
        // Dọn dẹp chat window và reset state
        chatWindow.empty();
        currentConversationId = 0;
        sidebarContent.find('.sidebar-item').removeClass('active');

        // Ẩn menu hành động
        chatActionsMenu.addClass('d-none');
        inputMode = 'quiz'; // Chuyển sang trạng thái tạo quiz

        // Gọi ajax để regen các quiz gen request cũ
        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa fa-robot"></i>
            </div>
        `);
        appendMessage(loadingEffect, true);

        ajax.call([{
            methodname: 'local_mychatbot_get_quiz_gen_history',
            args: {},
            done: function(data) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');

                if (data && data.length > 0) {
                    showQuizGenRequestHistory(data);
                } else {
                    showSystemMessage("Bạn chưa có yêu cầu tạo quiz nào.", "info");
                }
            },
            fail: function(ex) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi khi lấy lịch sử các yêu cầu tạo quiz: (${ex.message})`, "status-error");
            }
        }]);

        // Hiển thị Form Tạo Quiz
        $('#quiz-options-container').removeClass('d-none');

        // Đổi placeholder của ô nhập liệu để điều hướng người dùng
        chatInput.attr('placeholder', 'Nhập chủ đề Quiz...');
        chatInput.focus();
    }

    /**
     * Hiển thị lỗi nếu người dùng không nhập tin nhắn khi đang ở chế độ chat
     */
    function showChatInputError() {
        $('#input-error span').text('Vui lòng không bỏ trống tin nhắn.'); // Cập nhật nội dung lỗi
        $('#input-error').removeClass('d-none');
    }

    /**
     * Ẩn lỗi ô nhập liệu trong chế độ chat
     */
    function hideChatInputError() {
        $('#input-error span').text(''); // Xóa nội dung lỗi
        $('#input-error').addClass('d-none');
    }

    /**
     * Hiển thị lỗi nếu người dùng không nhập yêu cầu tạo quiz (prompt) khi đang ở chế độ tạo quiz
     */
    function showQuizPromptError() {
        $('#input-error span').text('Vui lòng nhập chủ đề Quiz.'); // Cập nhật nội dung lỗi
        $('#input-error').removeClass('d-none');
    }

    /**
     * Ẩn lỗi liên quan đến tạo quiz (lỗi không nhập prompt)
     */
    function hideQuizPromptError() {
        $('#input-error span').text(''); // Xóa nội dung lỗi
        $('#input-error').addClass('d-none');
    }

    /**
     * Hiển thị lỗi nếu người dùng không chọn số lượng câu hỏi ở bất kỳ độ khó nào khi đang ở chế độ tạo quiz
     */
    function showQuizDifficultyError() {
        $('#quiz-difficulty-error span').text('Vui lòng chọn số lượng câu hỏi ở ít nhất 1 độ khó.'); // Cập nhật nội dung lỗi
        $('#quiz-difficulty-error').removeClass('d-none');
    }

    /**
     * Ẩn lỗi liên quan đến tạo quiz (lỗi không chọn số lượng ở bất kì độ khó nào)
     */
    function hideQuizDifficultyError() {
        $('#quiz-difficulty-error span').text(''); // Xóa nội dung lỗi
        $('#quiz-difficulty-error').addClass('d-none');
    }

    /**
     * Kiểm tra xem người dùng đã chọn số lượng câu hỏi ở ít nhất 1 độ khó chưa khi đang ở chế độ tạo quiz
     */
    function validateQuizRequestData() {
        // Kiểm tra prompt (chủ đề quiz) - bắt buộc phải có
        let prompt = chatInput.val().trim();
        if (!prompt) {
            showQuizPromptError();
            return false;
        }

        // Kiểm tra số lượng câu hỏi ở mỗi độ khó, nếu người dùng để trống thì mặc định là 0
        let num_easy = parseInt($('#quiz-ai-easy').val()) || 0;
        let num_medium = parseInt($('#quiz-ai-medium').val()) || 0;
        let num_hard = parseInt($('#quiz-ai-hard').val()) || 0;

        const total = num_easy + num_medium + num_hard;

        if (total <= 0) {
            showQuizDifficultyError();
            return false;
        }

        hideQuizPromptError();
        hideQuizDifficultyError();
        return true;
    }

    /**
     * Tắt chế độ tạo Quiz, trở về Chat bình thường
     */
    function closeQuizMode() {
        inputMode = 'chat'; // Trả về trạng thái Chat

        chatWindow.find('.system-message.info').filter(function() {
            return $(this).text().includes("Bạn chưa có yêu cầu tạo quiz nào.");
        }).remove();

        hideQuizPromptError();
        hideQuizDifficultyError();

        $('#quiz-options-container').addClass('d-none');
        $('#quiz-ai-file').val(''); // Xóa file đã chọn (nếu có)
        $('#quiz-selected-file').addClass('d-none');

        // Reset lại ô nhập liệu
        chatInput.val('');
        chatInput.attr('placeholder', 'Nhập tin nhắn...');
        autoGrowTextarea(chatInput[0], true);
    }
    /**
     * Hiển thị tên file được upload
     */
    function displayUploadedFileName() {
        let quizFileInput = $('#quiz-ai-file');
        let quizSelectedFile = $('#quiz-selected-file');
        let file = quizFileInput[0].files[0];

        if (file) {
            $('#quiz-file-name').text(file.name);
            quizSelectedFile.removeClass('d-none');
        } else {
            quizSelectedFile.addClass('d-none');
        }
    }

    /**
     * Xóa file đã upload
     */
    function removeFileUpload() {
        $('#quiz-ai-file').val(''); // Reset file input
        $('#quiz-selected-file').addClass('d-none');
    }

    /**
     * update giá trị tổng số câu trên giao diện khi thay đổi số lượng câu hỏi ở bất kỳ độ khó nào
     */
    function updateTotal() {
        hideQuizPromptError(); // Ẩn lỗi ô nhập liệu nếu có
        hideQuizDifficultyError(); // Ẩn lỗi quiz nếu có

        const total = $('#quiz-total-count');

        const totalValue = (parseInt($('#quiz-ai-easy').val()) || 0) +
            (parseInt($('#quiz-ai-medium').val()) || 0) +
            (parseInt($('#quiz-ai-hard').val()) || 0);

        total.text(`Tổng: ${totalValue} câu`);
    }
    /**
     * Xử lý dữ liệu form và đọc file thành Base64 trước khi gọi API
     */
    function processQuizGenerationRequest() {
        let prompt = chatInput.val().trim(); // LẤY TRỰC TIẾP TỪ Ô NHẬP LIỆU CHÍNH
        let fileInput = $('#quiz-ai-file')[0];
        let num_easy = parseInt($('#quiz-ai-easy').val()) || 0;
        let num_medium = parseInt($('#quiz-ai-medium').val()) || 0;
        let num_hard = parseInt($('#quiz-ai-hard').val()) || 0;
        let userMsgText = `Yêu cầu tạo ${num_easy + num_medium + num_hard} câu hỏi.<br>`;

        let requestData = {
            prompt: prompt,
            num_easy: num_easy,
            num_medium: num_medium,
            num_hard: num_hard,
            filename: '',
            filedata: '', // Dành cho chuỗi Base64
            userrequest: ''
        };

        // Đóng form giao diện ngay khi bắt đầu xử lý để người dùng thấy chat window
        closeQuizMode();

        // Nếu có file, dùng FileReader để mã hóa thành Base64
        if (fileInput.files.length > 0) {
            let file = fileInput.files[0];
            requestData.filename = file.name;
            userMsgText += `Dựa trên tài liệu: <strong>${requestData.filename}</strong>`;
            requestData.userrequest = userMsgText;

            let reader = new FileReader();
            reader.onload = function(e) {
                // e.target.result có dạng "data:application/pdf;base64,JVBERi0xLjQK..."
                // Ta chỉ lấy phần nội dung đằng sau dấu phẩy
                let base64String = e.target.result.split(',')[1];
                requestData.filedata = base64String;
                sendQuizGenerationAjax(requestData);
            };
            reader.onerror = function() {
                notification.addNotification({ message: 'Lỗi khi đọc tài liệu tải lên.', type: 'error' });
            };
            // Đọc file dưới dạng URL Data (chứa Base64)
            reader.readAsDataURL(file);
        } else {
            userMsgText += `Chủ đề: <strong>${requestData.prompt}</strong>`;
            requestData.userrequest = userMsgText;
            // Nếu không có file, gửi đi luôn
            sendQuizGenerationAjax(requestData);
        }
    }
    /**
     * Hàm này sẽ được gọi sau khi đã có dữ liệu sẵn sàng (đọc file thành Base64 nếu có) để gửi yêu cầu tạo quiz lên backend
     * @param {Object} requestData - Dữ liệu đã được chuẩn bị sẵn sàng để gửi lên backend
     */
    function sendQuizGenerationAjax(requestData) {
        // Hiển thị một tin nhắn giả lập người dùng yêu cầu AI
        showUserMessage(requestData.userrequest, getCurrentTime(), true);

        // Hiệu ứng Loading
        chatbotContainer.removeClass('no-before no-after');
        const loadingEffect = $('<div>').addClass('pulse-container bot-loading');
        loadingEffect.html(`
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="pulse-ring"></div>
            <div class="core-circle">
                <i class="fa-solid fa-wand-magic-sparkles text-warning">
                </i>
            </div>
        `);
        appendMessage(loadingEffect, true);

        // Gọi Web Service
        ajax.call([{
            methodname: 'local_mychatbot_generate_quiz',
            args: requestData,
            done: function(data) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');

                if (data && data.questions && data.questions.length > 0 && data.request_id) {
                    showQuizPreview(data.questions, data.request_id);
                }
                else {
                    showSystemMessage("Không nhận được dữ liệu câu hỏi từ chatbot.", "info");
                }
            },
            fail: function(ex) {
                loadingEffect.remove();
                chatbotContainer.addClass('no-before no-after');
                notification.exception(ex);
                showSystemMessage(`Lỗi gọi API: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Hiển thị bản Xem trước (Preview) các câu hỏi và nút "Lưu vào khóa học"
     * @param {Array} questions - Danh sách câu hỏi đã được AI tạo ra, mỗi câu hỏi có thể có cấu trúc như sau:
     * {
     *   "question_text": "Câu hỏi 1",
     *   "options": ["Đáp án 1", "Đáp án 2", "Đáp án 3", "Đáp án 4"],
     *   "correct_answer_index": 0,
     *   "explanation": "Giải thích cho câu hỏi 1"
     * }
     * @param {number} request_id - ID của yêu cầu tạo quiz nhằm mục đích tracking sau này
     */
    function showQuizPreview(questions, request_id) {
        if (!questions || questions.length === 0) {
            showSystemMessage("AI không tạo được câu hỏi nào từ nội dung này.", "warning");
            return;
        }

        const botMessageWrapper = $('<div>').addClass('bot-message-wrapper');
        const botAvatarIcon = $('<i>').addClass('fa-solid fa-robot mr-2');
        const botMessageContent = $('<div>').addClass('bot-message');

        let previewHtml = `
            <h6 class="mb-3 border-bottom pb-2 text-success">
                <i class="fa fa-check-circle"></i> AI đã soạn xong ${questions.length} câu hỏi!
            </h6>
        `;
        previewHtml += `<p class="small text-muted mb-2">Vui lòng chọn các câu hỏi bạn muốn lưu:</p>`;
        previewHtml += `<div class="quiz-preview-list" style="max-height: 300px; overflow-y: auto; font-size: 0.85rem;">`;

        // Bây giờ, mỗi question sẽ có thêm độ khó (level) là easy/medium/hard,
        // nên cần lọc nhóm câu hỏi theo độ khó trước khi render
        let easyQuestions = questions.filter(q => q.level == 'easy');
        let mediumQuestions = questions.filter(q => q.level == 'medium');
        let hardQuestions = questions.filter(q => q.level == 'hard');
        // Lặp qua từng câu hỏi để render
        let index = 0; // Biến index dùng chung để đánh số câu hỏi liên tục giữa các độ khó
        // Đầu tiên render câu hỏi dễ, sau đó đến trung bình và khó, nhưng index vẫn tăng liên tục để đánh số câu hỏi
        // Thêm tiêu đề từng độ khó trước khi render câu hỏi của độ khó đó
        if (easyQuestions.length > 0) {
            previewHtml += `<div class="my-2 text-success"><strong>Dễ (Ghi nhớ):</strong></div>`;
            easyQuestions.forEach((q) => {
                previewHtml += `
                    <div class="p-2 mb-2 border rounded bg-white d-flex align-items-start question-preview-item">
                        <input type="checkbox" class="mt-1 mr-2 quiz-question-checkbox" checked data-index="${index}">
                        <div class="flex-grow-1">
                            <strong>Câu ${index + 1}: ${q.question_text}</strong>
                            <ul class="pl-3 mb-1 mt-1" style="list-style-type: lower-alpha;">
                `;
                q.options.forEach((opt, optIndex) => {
                    let isCorrect = (optIndex === q.correct_answer_index);
                    let textStyle = isCorrect ? 'color: green; font-weight: bold;' : '';
                    let checkMark = isCorrect ? ' <i class="fa fa-check text-success"></i>' : '';
                    previewHtml += `<li style="${textStyle}">${opt}${checkMark}</li>`;
                });

                previewHtml += `
                            </ul>
                            <div class="text-muted small"><em>Giải thích: ${q.explanation}</em></div>
                        </div>
                    </div>
                `;
                index++;
            });
        }
        if (mediumQuestions.length > 0) {
            previewHtml += `<div class="my-2 text-primary"><strong>Trung bình (Thông hiểu):</strong></div>`;
            mediumQuestions.forEach((q) => {
                previewHtml += `
                    <div class="p-2 mb-2 border rounded bg-white d-flex align-items-start question-preview-item">
                        <input type="checkbox" class="mt-1 mr-2 quiz-question-checkbox" checked data-index="${index}">
                        <div class="flex-grow-1">
                            <strong>Câu ${index + 1}: ${q.question_text}</strong>
                            <ul class="pl-3 mb-1 mt-1" style="list-style-type: lower-alpha;">
                `;

                q.options.forEach((opt, optIndex) => {
                    let isCorrect = (optIndex === q.correct_answer_index);
                    let textStyle = isCorrect ? 'color: green; font-weight: bold;' : '';
                    let checkMark = isCorrect ? ' <i class="fa fa-check text-success"></i>' : '';
                    previewHtml += `<li style="${textStyle}">${opt}${checkMark}</li>`;
                });

                previewHtml += `
                            </ul>
                            <div class="text-muted small"><em>Giải thích: ${q.explanation}</em></div>
                        </div>
                    </div>
                `;
                index++;
            });
        }
        if (hardQuestions.length > 0) {
            previewHtml += `<div class="my-2 text-warning"><strong>Khó (Vận dụng):</strong></div>`;
            hardQuestions.forEach((q) => {
                previewHtml += `
                    <div class="p-2 mb-2 border rounded bg-white d-flex align-items-start question-preview-item">
                        <input type="checkbox" class="mt-1 mr-2 quiz-question-checkbox" checked data-index="${index}">
                        <div class="flex-grow-1">
                            <strong>Câu ${index + 1}: ${q.question_text}</strong>
                            <ul class="pl-3 mb-1 mt-1" style="list-style-type: lower-alpha;">
                `;

                q.options.forEach((opt, optIndex) => {
                    let isCorrect = (optIndex === q.correct_answer_index);
                    let textStyle = isCorrect ? 'color: green; font-weight: bold;' : '';
                    let checkMark = isCorrect ? ' <i class="fa fa-check text-success"></i>' : '';
                    previewHtml += `<li style="${textStyle}">${opt}${checkMark}</li>`;
                });

                previewHtml += `
                            </ul>
                            <div class="text-muted small"><em>Giải thích: ${q.explanation}</em></div>
                        </div>
                    </div>
                `;
                index++;
            });
        }
        previewHtml += `</div>`;

        // Nút Lưu (Ban đầu ở trạng thái enabled vì mặc định là chọn tất cả)
        previewHtml += `
            <button class="btn btn-success btn-sm w-100 mt-2 btn-save-quiz-to-moodle">
                <i class="fa fa-save"></i> Lưu <span class="selected-count">${questions.length}</span> câu đã chọn
            </button>
        `;

        botMessageContent.html(previewHtml);
        botMessageWrapper.append(botAvatarIcon).append(botMessageContent);
        appendMessage(botMessageWrapper, true);

        // --- LOGIC XỬ LÝ CHỌN CÂU HỎI ---
        const saveBtn = botMessageContent.find('.btn-save-quiz-to-moodle');
        const checkboxes = botMessageContent.find('.quiz-question-checkbox');
        const countDisplay = saveBtn.find('.selected-count');

        // Lắng nghe sự kiện thay đổi trên các checkbox
        checkboxes.off('change').on('change', function() {
            let checkedCount = checkboxes.filter(':checked').length;
            // Cập nhật số lượng hiển thị trên nút
            countDisplay.text(checkedCount);
            // Bật/Tắt nút Lưu: Chỉ cho phép click nếu có ít nhất 1 câu được chọn
            if (checkedCount > 0) {
                saveBtn.prop('disabled', false);
                saveBtn.removeClass('btn-secondary').addClass('btn-success');
            } else {
                saveBtn.prop('disabled', true);
                saveBtn.removeClass('btn-success').addClass('btn-secondary');
            }
        });

        // Gắn sự kiện click cho nút "Lưu vào ngân hàng câu hỏi"
        saveBtn.off('click').on('click', function() {
            // Lọc ra danh sách câu hỏi thực sự được chọn
            let selectedQuestions = [];
            checkboxes.filter(':checked').each(function() {
                let index = $(this).data('index');
                selectedQuestions.push(questions[index]);
            });
            executeSaveQuizAction(selectedQuestions, request_id, saveBtn, checkboxes);
        });
    }
    /**
     * Hàm thực hiện gọi AJAX để lưu danh sách câu hỏi đã lọc
     * @param {Array} selectedQuestions - Mảng các câu hỏi đã được người dùng chọn để lưu
     * @param {number} request_id - ID của yêu cầu tạo quiz nhằm mục đích tracking để cập nhật cột saved của yêu cầu đó trong db
     * @param {Object} saveBtn - Đối tượng jQuery của nút "Lưu vào ngân hàng câu hỏi"
     * @param {Object} checkboxes - Đối tượng jQuery của các checkbox câu hỏi, dùng để vô hiệu hóa sau khi lưu thành công
     */
    function executeSaveQuizAction(selectedQuestions, request_id, saveBtn, checkboxes) {
        let urlParams = new URLSearchParams(window.location.search);
        let courseId = parseInt(urlParams.get('id'));

        if (!courseId || isNaN(courseId)) {
            notification.addNotification({
                message: 'Không tìm thấy ID khóa học. Vui lòng mở chatbot tại trang một khóa học cụ thể.',
                type: 'error'
            });
            return;
        }

        saveBtn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Đang lưu...');

        ajax.call([{
            methodname: 'local_mychatbot_save_quiz_questions',
            args: {
                courseid: courseId,
                request_id: request_id,
                questionsjson: JSON.stringify(selectedQuestions) // Chỉ gửi những câu đã chọn
            },
            done: function(data) {
                if (data.status === 'success') {
                    saveBtn.removeClass('btn-success').addClass('btn-secondary')
                           .html('<i class="fa fa-check"></i> Hoàn tất');
                    // Vô hiệu hóa checkbox sau khi lưu thành công
                    checkboxes.prop('disabled', true);
                    showSystemMessage(data.message, "status-ok");
                    notification.addNotification({ message: data.message, type: 'success' });
                } else {
                    saveBtn.prop('disabled', false).html('<i class="fa fa-save"></i> Thử lại');
                    showSystemMessage(data.message, "status-error");
                }
            },
            fail: function(ex) {
                saveBtn.prop('disabled', false).html('<i class="fa fa-save"></i> Thử lại');
                notification.exception(ex);
                showSystemMessage(`Lỗi khi lưu câu hỏi: (${ex.message})`, "status-error");
            }
        }]);
    }
    /**
     * Initialize the chatbot (khởi tạo chatbot, gán event listeners, v.v.)
     */
    var init = function() {
        $(document).ready(function() {
            chatbotContainer = $('#chatbot-container');
            chatWindow = $('#chat-window');
            chatInput = $('#chat-input');
            sendButton = $('#send-btn');
            closeButton = $('#chatbot-close-btn');
            chatActionsButton = $('#chat-actions-btn');
            chatActionsMenu = $('#chat-actions-menu');
            sidebar= $('#chatbot-sidebar');
            sidebarEmpty = $('#sidebar-empty');
            sidebarContent = $('#sidebar-content');
            sidebarToggleBtn = $('#sidebar-toggle-btn');
            if (
                !chatbotContainer.length ||
                !chatWindow.length ||
                !chatInput.length ||
                !sendButton.length ||
                !closeButton.length ||
                !chatActionsButton.length ||
                !chatActionsMenu.length ||
                !sidebar.length ||
                !sidebarEmpty.length ||
                !sidebarContent.length ||
                !sidebarToggleBtn.length
            ) {
                return;
            }
            setTimeout(function() {
                autoGrowTextarea(chatInput[0], true);
            }, 0);

            chatInput.off('input').on('input', function() {
                if (inputMode === 'quiz') {
                    // Ở chế độ tạo quiz, khi người dùng nhập yêu cầu thì ẩn lỗi nếu có
                    hideQuizPromptError();
                    hideQuizDifficultyError();
                } else {
                    hideChatInputError(); // Ẩn lỗi chung của ô nhập liệu (nếu có)
                }

                if ($(this).val().trim().length > 0) {
                    autoGrowTextarea(this);
                }
                else {
                    autoGrowTextarea(this, true);
                }
            });
            chatInput.off('keypress').on('keypress', function(e) {
                // gửi tin nhắn bằng Enter
                if (e.which === 13 && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
            // Gửi tin nhắn bằng nút Gửi
            sendButton.off('click').on('click', function(e) {
                e.preventDefault();
                sendMessage();
            });

            closeButton.off('click').on('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleChatbot();
            });

            // Thêm event listener cho nút actions
            if (chatActionsButton.length) {
                chatActionsButton.off('click').on('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (inputMode === 'quiz') {
                        hideQuizPromptError();
                        hideQuizDifficultyError();
                    } else {
                        hideChatInputError();
                    }
                    toggleChatActionsMenu();
                });
            }

            // Thêm event listener cho nút toggle sidebar
            sidebarToggleBtn.off('click').on('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                if (inputMode === 'quiz') {
                    hideQuizPromptError();
                    hideQuizDifficultyError();
                } else {
                    hideChatInputError();
                }

                if (chatbotContainer.hasClass('sidebar-expanded')) {
                    sidebarEmpty.addClass('d-none');
                    sidebarContent.addClass('d-none');
                    chatbotContainer.removeClass('sidebar-expanded');
                } else {
                    chatbotContainer.addClass('sidebar-expanded');
                    // Kiểm tra có cuộc hội thoại nào không
                    if (NoConversation) {
                        sidebarEmpty.removeClass('d-none');
                        sidebarContent.addClass('d-none');
                    } else {
                        sidebarEmpty.addClass('d-none');
                        sidebarContent.removeClass('d-none');
                    }
                }
            });

            // Thêm event listeners cho các mục trong menu
            if (chatActionsMenu.length) {
                chatActionsMenu.find('.chat-action-item').off('click').on('click', function(e) {
                    e.stopPropagation();
                    var action = $(this).data('action');
                    switch(action) {
                        case 'new_chat':
                            handleNewChat();
                            break;
                        case 'quiz_reminder':
                            handleQuizReminderClick();
                            break;
                        case 'assignment_reminder':
                            handleAssignmentReminderClick();
                            break;
                        case 'course_progress':
                            handleCourseProgressClick();
                            break;
                        case 'create_quiz':
                            handleCreateQuizClick();
                            break;
                    }
                    chatActionsMenu.addClass('d-none'); // Đóng menu
                });
            }

            // Bắt sự kiện click vào tên học viên trên Tooltip của biểu đồ
            chatWindow.off('click', '.student-detail-link').on('click', '.student-detail-link', function(e) {
                e.preventDefault();
                e.stopPropagation(); // Ngăn sự kiện nổi bọt

                let userId = $(this).data('userid');
                let courseId = $(this).data('courseid');
                // Trích xuất tên (xóa dấu chấm tròn và phần % phía sau)
                let rawText = $(this).text();
                let studentName = rawText.replace('• ', '').split(' (')[0].trim();

                handleStudentProgressClick(courseId, userId, studentName);
            });

            // Đăng ký sự kiện cho nút Hủy chế độ tạo Quiz
            $('#btn-cancel-quiz-mode').off('click').on('click', function(e) {
                e.preventDefault();
                closeQuizMode();
            });

            // Đăng ký sự kiện cho input file để hiển thị tên file khi người dùng chọn
            $('#quiz-ai-file').off('change').on('change', displayUploadedFileName);

            // Đăng ký sự kiện cho nút Xóa file đã chọn
            $('#quiz-remove-file').off('click').on('click', function(e) {
                e.preventDefault();
                removeFileUpload();
            });

            // Đăng ký sự kiện drop, dragover và dragleave cho khu vực upload file cho hiệu ứng drag & drop
            $('.quiz-upload-area').off('dragover').on('dragover', function(e) {
                e.preventDefault();
                $(this).addClass('dragging');
            });
            $('.quiz-upload-area').off('dragleave').on('dragleave', function() {
                $(this).removeClass('dragging');
            });
            $('.quiz-upload-area').off('drop').on('drop', function(e) {
                e.preventDefault();
                $(this).removeClass('dragging');

                // Lấy file từ sự kiện drag & drop
                const files = e.originalEvent.dataTransfer.files;
                if (files.length) {
                    $('#quiz-ai-file')[0].files = files; // Gán file vào input

                    let file = files[0];
                    $('#quiz-file-name').text(file.name);
                    $('#quiz-selected-file').removeClass('d-none');
                }
            });

            // Lắng nghe thay đổi số lượng câu hỏi ở mỗi độ khó để cập nhật tổng số câu hỏi
            $('#quiz-ai-easy').add($('#quiz-ai-medium')).add($('#quiz-ai-hard')).on('input', updateTotal);

            // Đóng menu khi click ra ngoài
            $(document).on('click', function(event) {
                if (chatActionsMenu && !chatActionsMenu.hasClass('d-none')) {
                    if (!$(event.target).closest('#chat-actions-container').length) {
                        chatActionsMenu.addClass('d-none');
                    }
                }
            });
        });
    };
    /**
     * Insert icon into navbar
     */
    var injectIcon = function() {
        $(document).ready(function()
        {
            var targetContainer = $('#usernavigation');
            if (targetContainer && targetContainer.length) {
                targetContainer.append(
                    $('<div>').addClass('divider border-left h-75 align-self-center ml-1 mr-3')
                );
                chatbotIcon = $('<div>').attr('id', 'chatbot-icon-trigger').append(
                    `<a href="#" class="nav-link" title="Moodle Chatbot" aria-label="Moodle Chatbot">
                        <i id="chatbot-custom-icon" class="fa-solid fa-robot"></i>
                    </a>`
                );
                targetContainer.append(chatbotIcon);
                if (chatbotIcon.length) {
                    chatbotIcon.off('click').on('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        toggleChatbot();
                    });
                }
            }
        });
    };
    /**
     * Check user capability and show/hide chatbot chat actions menu accordingly
     * Kiểm tra quyền của người dùng (là học viên trong ít nhất 1 khóa học hay không, giảng viên trong ít nhất 1 khóa học hay không)
     * Một người dùng có thể là student, teacher hoặc cả 2
     * Ẩn hiện các nhóm chức năng tương ứng theo quyền người dùng trong phần chatActionsMenu
     */
    var checkCapability = function() {
        $(document).ready(function() {
            ajax.call([{
                methodname: 'local_mychatbot_check_capability',
                args: {},
                done: function(data) {
                    // Nếu data.student là true, người dùng là học viên của ít nhất 1 khóa học
                    // Nếu data.teacher là true, người dùng là giảng viên của ít nhất 1 khóa học
                    if (data && data.student) {
                        chatActionsMenu.find('.student-action').removeClass('d-none');
                    }
                    if (data && data.teacher) {
                        chatActionsMenu.find('.teacher-action').removeClass('d-none');
                    }
                },
                fail: function(ex) {
                    notification.exception(ex);
                }
            }]);
        });
    };
    return {
        init: init,
        injectIcon: injectIcon,
        checkCapability: checkCapability
    };
});