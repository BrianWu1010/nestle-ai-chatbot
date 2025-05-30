class Chatbox {
    constructor() {
        this.args = {
            openButton: document.querySelector('.chatbox__button'),
            chatBox: document.querySelector('.chatbox__support'),
            sendButton: document.querySelector('.send__button')
        }

        this.state = false;
        this.messages = [];
    }

    display() {
        const {openButton, chatBox, sendButton} = this.args;

        openButton.addEventListener('click', () => this.toggleState(chatBox))

        sendButton.addEventListener('click', () => this.onSendButton(chatBox))

        const node = chatBox.querySelector('input');
        node.addEventListener("keyup", ({key}) => {
            if (key === "Enter") {
                this.onSendButton(chatBox)
            }
        })
    }

    toggleState(chatbox) {
        this.state = !this.state;

        if(this.state) {
            chatbox.classList.add('chatbox--active');
            chatbox.style.width = "600px";
            chatbox.style.height = "600px";

            // Check if greeting has already been shown
            if (this.messages.length === 0) {
                fetch('http://127.0.0.1:8000/greet')
                    .then(res => res.json())
                    .then(data => {
                        const greeting = data.greeting || "Hi, I'm Smartie! How can I assist you today?";
                        const msg = { name: "Sam", message: greeting };
                        this.messages.push(msg);
                        this.updateChatText(chatbox);
                    })
                    .catch(err => {
                        console.error('Greeting fetch error:', err);
                        const fallbackGreeting = "Hi, I'm Smartie! How can I assist you today?";
                        const msg = { name: "Sam", message: fallbackGreeting };
                        this.messages.push(msg);
                        this.updateChatText(chatbox);
                    });
            }

        } else {
            chatbox.classList.remove('chatbox--active');
        }
    }

    onSendButton(chatbox) {
        var textField = chatbox.querySelector('input');
        let text1 = textField.value
        if (text1 === "") {
            return;
        }

        let msg1 = { name: "User", message: text1 }
        this.messages.push(msg1);

        fetch('http://127.0.0.1:8000/search', {
            method: 'POST',
            body: JSON.stringify({ query: text1 }),
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(r => r.json())
        .then(r => {
            const combinedAnswer = r.results.map(item => item.content).join("\n\n");
            let msg2 = { name: "Sam", message: combinedAnswer };
            this.messages.push(msg2);
            this.updateChatText(chatbox);
            textField.value = '';
        })
        .catch((error) => {
            console.error('Error:', error);
            this.updateChatText(chatbox);
            textField.value = '';
        });
    }

    updateChatText(chatbox) {
        var html = '';
        this.messages.slice().reverse().forEach(function(item, index) {
            if (item.name === "Sam")
            {
                html += '<div class="messages__item messages__item--visitor">' + item.message + '</div>'
            }
            else
            {
                html += '<div class="messages__item messages__item--operator">' + item.message + '</div>'
            }
          });

        const chatmessage = chatbox.querySelector('.chatbox__messages');
        chatmessage.innerHTML = html;
    }
}


const chatbox = new Chatbox();
chatbox.display();