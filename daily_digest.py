import os
import re
import openai
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from _secrets import OPENAI_API_KEY, GMAIL_APP_PASSWORD
openai.api_key = OPENAI_API_KEY
sender_email = "mahler83@gmail.com"

# set the number of recent daily notes to open
NUM_DAILY_NOTES = 1

# find the most recent daily notes files
daily_notes_dir = "./Research/Daily notes/"
daily_notes_files = os.listdir(daily_notes_dir)
daily_notes_files.sort(reverse=True)
recent_daily_notes = daily_notes_files[:NUM_DAILY_NOTES]

# read the contents of the recent daily notes files and get their creation times
daily_notes_contents = []
daily_notes_ctime = []
for note_file in recent_daily_notes:
    with open(daily_notes_dir + note_file, "r", encoding="utf-8") as f:
        contents = f.read()
        daily_notes_contents.append("\n" + os.path.splitext(note_file)[0] + "\n" + contents.strip() + "\n")
    daily_notes_ctime.append(os.path.getctime(daily_notes_dir + note_file))

# find all internal links in the daily notes contents and get their creation times
def find_file(filename, directory="./Research"):
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        if filename + ".md" in files:
            print(f"[FOUND] {root.replace("\\", "/")}/{filename}.md")
            return os.path.join(root.replace("\\", "/"), filename + ".md")
    return "./Research/Notes/" + filename + ".md"

internal_links = re.findall(r'\[\[([^|\]]*?)\]\]', "".join(daily_notes_contents))

# Create a dictionary to store the note_file and its corresponding creation time
linked_notes = {}
for link in internal_links:
    note_file = find_file(link)
    linked_notes[note_file] = os.path.getctime(note_file)

# combine the daily notes contents and linked notes contents in chronological order
daily_digest = ""
for ctime in sorted(daily_notes_ctime + list(linked_notes.values())):
    if ctime in daily_notes_ctime:
        daily_digest += daily_notes_contents[daily_notes_ctime.index(ctime)]
    else:
        note_file = [k for k, v in linked_notes.items() if v == ctime][0]
        with open(note_file, "r", encoding="utf-8") as f:
            contents = f.read()
            daily_digest += "\n" + os.path.splitext(os.path.basename(note_file))[0] + "\n" + contents.strip() + "\n"
    daily_digest += "\n"

# remove blank lines
daily_digest = re.sub(r'[\r\n]+(\s*[\r\n])+', '\n', daily_digest)

# right-strip all lines
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
daily_digest = re.sub(r'[\r\n]+(\s*[\r\n])+', '\n', daily_digest)

# save the daily digest to a file
with open("daily_digest.txt", "w", encoding="utf-8") as f:
    f.write(daily_digest)

system_prompt = "Summarize yesterday's research log provided by me. Also, propose 3 things that can be done today. Use bullet points."
user_prompt = daily_digest

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

#Send email
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


# Set up your email credentials
sender_name = "Obsidian assistant"
recipient_email = sender_email
recipient_name = "My master"
subject = "Your daily log"

# Send the email
send_email(subject, answer, recipient_name, recipient_email, sender_name, sender_email, GMAIL_APP_PASSWORD)
