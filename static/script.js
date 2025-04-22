document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');
    const chatMessages = document.getElementById('chat-messages');
    const recordingIndicator = document.getElementById('recording-indicator');
    const stopRecordingButton = document.getElementById('stop-recording');
    
    let mediaRecorder;
    let audioChunks = [];
    
    // Send message when send button is clicked
    sendButton.addEventListener('click', sendMessage);
    
    // Send message when Enter key is pressed
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    // Function to send message
    function sendMessage() {
        const message = messageInput.value.trim();
        if (message.length === 0) return;
        
        addMessage(message, 'user');
        messageInput.value = '';
        
        // Send message to server
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'message=' + encodeURIComponent(message)
        })
        .then(response => response.json())
        .then(data => handleServerResponse(data))
        .catch(error => console.error('Error:', error));
    }
    
    // Handle bot response
    function handleServerResponse(data) {
        if (data.response) {
            addMessage(data.response.text, "bot");
    
            if (data.response.buttons && data.response.buttons.length > 0) {
                const buttonContainer = document.createElement('div');
                buttonContainer.className = 'button-container';
    
                data.response.buttons.forEach(button => {
                    const btn = document.createElement('button');
                    btn.textContent = button.text;
                    btn.className = 'chat-button';
                    btn.addEventListener('click', () => {
                        messageInput.value = button.value;
                        sendMessage();
                    });
                    buttonContainer.appendChild(btn);
                });
    
                chatMessages.appendChild(buttonContainer);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        }
    }
    
    
    // Add message to chat
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = sender === 'user' ? 'message user-message' : 'message bot-message';
        
        // Process text with line breaks
        const formattedText = text.replace(/\n/g, '<br>');
        
        // Get current time
        const now = new Date();
        const timeString = now.getHours() + ':' + (now.getMinutes() < 10 ? '0' : '') + now.getMinutes();
        
        messageDiv.innerHTML = formattedText + `<span class="time">${timeString} ${sender === 'user' ? '<span class="double-check-icon"></span>' : ''}</span>`;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Speech Recognition Setup
    if ('MediaRecorder' in window) {
        micButton.addEventListener('click', toggleRecording);
        stopRecordingButton.addEventListener('click', stopRecording);
    } else {
        micButton.style.display = 'none';
    }
    
    function toggleRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            stopRecording();
        } else {
            startRecording();
        }
    }
    
    function startRecording() {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.addEventListener('dataavailable', event => {
                    audioChunks.push(event.data);
                });
                
                mediaRecorder.addEventListener('stop', () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    sendAudioToServer(audioBlob);
                    
                    // Stop all tracks in the stream to release the microphone
                    stream.getTracks().forEach(track => track.stop());
                });
                
                mediaRecorder.start();
                recordingIndicator.classList.remove('hidden');
            })
            .catch(error => {
                console.error('Error accessing microphone:', error);
                alert('Error accessing microphone. Please check your permissions.');
            });
    }
    
    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            recordingIndicator.classList.add('hidden');
        }
    }
    
    function sendAudioToServer(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.wav');
        
        fetch('/speech', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.transcript) {
                addMessage(data.transcript, 'user');
            }
            if (data.response) {
                handleServerResponse(data);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            addMessage('Error processing speech. Please try again.', 'bot');
        });
    }
});
// Dark mode toggle logic
const darkModeToggle = document.getElementById('dark-mode-toggle');
const darkModeIcon = document.getElementById('dark-mode-icon');

function setDarkMode(enabled) {
    if (enabled) {
        document.body.classList.add('dark-mode');
        darkModeIcon.textContent = 'light_mode';
        localStorage.setItem('theme', 'dark');
    } else {
        document.body.classList.remove('dark-mode');
        darkModeIcon.textContent = 'dark_mode';
        localStorage.setItem('theme', 'light');
    }
}

// On load, set theme from localStorage or system preference
(function() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setDarkMode(savedTheme === 'dark' || (!savedTheme && prefersDark));
})();

darkModeToggle.addEventListener('click', () => {
    setDarkMode(!document.body.classList.contains('dark-mode'));
});

