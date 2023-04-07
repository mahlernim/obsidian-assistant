import os
import re
import openai
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from _secrets import OPENAI_API_KEY, GMAIL_APP_PASSWORD

openai.api_key = OPENAI_API_KEY
sender_email = "mahler83@gmail.com"
NUM_DAILY_NOTES = 1
daily_notes_dir = "./Research/Daily notes/"

def check_daily_digest_processed(recent_daily_notes):
    try:
        with open("daily_digest.txt", "r", encoding="utf-8") as f:
            first_line = f.readline().strip()

        first_note_date = os.path.splitext(recent_daily_notes[0])[0].strip()
        return first_line == first_note_date
    except FileNotFoundError:
        return False

def get_recent_daily_notes():
    daily_notes_files = os.listdir(daily_notes_dir)
    daily_notes_files.sort(reverse=True)
    return daily_notes_files[:NUM_DAILY_NOTES]

def get_notes_content_and_ctime(note_files):
    contents = []
    ctimes = []
    for note_file in note_files:
        file_path = daily_notes_dir + note_file
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            contents.append("\n" + os.path.splitext(note_file)[0] + "\n" + content.strip() + "\n")
        ctimes.append(os.path.getctime(file_path))
    return contents, ctimes

def find_file(filename, directory="./Research"):
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        if filename + ".md" in files:
            print("[FOUND] " + root.replace("\\", "/") + f"/{filename}.md")
            return os.path.join(root.replace("\\", "/"), filename + ".md")
    return "./Research/Notes/" + filename + ".md"

def get_linked_notes(internal_links):
    linked_notes = {}
    for link in internal_links:
        note_file = find_file(link)
        linked_notes[note_file] = os.path.getctime(note_file)
    return linked_notes

def create_daily_digest(daily_notes_contents, daily_notes_ctime, linked_notes):
    daily_digest = ""

    # Add daily_note_contents to daily_digest first
    for content in daily_notes_contents:
        daily_digest += content
        daily_digest += "\n"

    # Add the sorted linked_notes content to daily_digest
    for ctime in sorted(list(linked_notes.values())):
        note_file = [k for k, v in linked_notes.items() if v == ctime][0]
        with open(note_file, "r", encoding="utf-8") as f:
            contents = f.read()
            daily_digest += "\n" + os.path.splitext(os.path.basename(note_file))[0] + "\n" + contents.strip() + "\n"
        daily_digest += "\n"

    # remove blank lines, right-strip all lines
    daily_digest = re.sub(r'[\r\n]+(\s*[\r\n])+', '\n', daily_digest)
    daily_digest = "\n".join([line.rstrip() for line in daily_digest.split("\n")])

    # delete lines that start with '#' and the next line is only '-'
    daily_digest = re.sub(r'(?m)^#\s+.+\n-\s*\n', '', daily_digest)

    # delete all but {title} from link pattern '[{title}]({link})'
    daily_digest = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', daily_digest)

    # delete code blocks that exceed 80 characters
    code_block_pattern = r'```(?:\n|.)*?(?<!\n)\n```'
    code_blocks = re.findall(code_block_pattern, daily_digest, flags=re.DOTALL)
    for code_block in code_blocks:
        if len(code_block) > 80:
            daily_digest = daily_digest.replace(code_block, '')

    # remove lines that start with "![[", "<<"
    daily_digest = re.sub(r'^(!\[\[|<<).*$', '', daily_digest, flags=re.MULTILINE)

    # replace "[ ]" with "unfinished: ", "[x]" with "finished: "
    daily_digest = re.sub(r'\[ \]', 'unfinished: ', daily_digest)
    daily_digest = re.sub(r'\[x\]', 'finished: ', daily_digest)

    # remove "[[", "]]"
    daily_digest = re.sub(r'\[\[|\]\]', '', daily_digest)

    # remove blank lines again
    daily_digest = re.sub(r'-\r\n', '', daily_digest)
    daily_digest = re.sub(r'[\r\n]+(\s*[\r\n])+', '\n', daily_digest)
    daily_digest = daily_digest.strip()
    
    return daily_digest


def save_daily_digest(daily_digest):
    with open("daily_digest.txt", "w", encoding="utf-8") as f:
        f.write(daily_digest)

def get_obsidian_assistant_response(system_prompt, user_prompt):
    print("Asking my Obsidian assistant...")
    completion = openai.ChatCompletion.create(
        model = "gpt-3.5-turbo",
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    answer = completion.choices[0].message.content
    print("Answer received!")
    print(answer)

    with open("obsidian_assistant_response.txt", "w", encoding="utf-8") as f:
        f.write(answer)
    return answer

def send_email(subject, body, recipient_name, recipient_email, sender_name, sender_email, password):
    msg = MIMEMultipart()
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = f"{recipient_name} <{recipient_email}>"
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Error sending email: {e}")

def main():
    # Create daily_digest
    recent_daily_notes = get_recent_daily_notes()
    if check_daily_digest_processed(recent_daily_notes):
        proceed = input("The daily digest seems to be already processed. Do you still want to continue? (y/n): ")
        if proceed.lower() != 'y':
            print("Aborting.")
            return
    daily_notes_contents, daily_notes_ctime = get_notes_content_and_ctime(recent_daily_notes)
    internal_links = re.findall(r'\[\[([^|\]]*?)\]\]', "".join(daily_notes_contents))
    linked_notes = get_linked_notes(internal_links)
    daily_digest = create_daily_digest(daily_notes_contents, daily_notes_ctime, linked_notes)
    save_daily_digest(daily_digest)
    
    # Ask ChatGPT for summary and suggestions
    system_prompt = "Summarize yesterday's research log provided by me. Also, propose 3 things that can be done today. Use bullet points."
    user_prompt = daily_digest
    answer = get_obsidian_assistant_response(system_prompt, user_prompt)
    
    # Send email
    sender_name = "ChatGPT Obsidian assistant"
    recipient_email = sender_email
    recipient_name = "My master"
    first_note_date = os.path.splitext(recent_daily_notes[0])[0].strip()
    subject = f"Your daily log for {first_note_date}"
    send_email(subject, answer, recipient_name, recipient_email, sender_name, sender_email, GMAIL_APP_PASSWORD)

if __name__ == "__main__":
    main()
