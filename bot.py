from apscheduler.schedulers.background import BackgroundScheduler
import socket, re, requests, threading

class Bot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.socket = None

        self.users = {}

        self.stopping = False

    def chat(self, msg):
        self.socket.send("PRIVMSG {} :{}\r\n".format(self.cfg.channel, msg).encode("utf-8"))

    def ban(self, user):
        chat(".ban {}".format(user))

    def timeout(self, user, secs=600):
        chat(".timeout {}".format(user, secs))

    def is_channel_live(self):
        response = requests.get("https://api.twitch.tv/kraken/streams/{}".format(self.cfg.channel[1:]), headers={"Client-ID": self.cfg.client_id})
        return bool(response.json()["stream"])

    def get_user_rank(self, user):
        if user in self.users:
            return self.users[user]["rank"]
        else:
            return None

    def on_message(self, user, message):
        return

    def on_command(self, user, command, args):
        return

    def on_join(self, user):
        return

    def on_leave(self, user):
        return

    def _check_irc(self):
        while not self.stopping:
            line = self.socket.recv(4096).decode("utf-8")

            if line == "PING :tmi.twitch.tv\r\n":
                self.socket.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))

            match = re.search(r"^:([a-zA-Z0-9_]+)\![a-zA-Z0-9_]+@[a-zA-Z0-9_]+\.tmi\.twitch\.tv PRIVMSG (#[a-zA-Z0-9_]+) :(.+)\r\n$", line)
            if match:
                user = match.group(1)
                channel = match.group(2)
                message = match.group(3)

                if message.startswith("!"):
                    command = message.split(" ", 1)
                    self.on_command(user, command[0][1:], command[1] if len(command) > 1 else "")
                else:
                    self.on_message(user, message)

    def _check_twitch(self):
        users_json = requests.get(url="https://tmi.twitch.tv/group/user/{}/chatters".format(self.cfg.channel[1:])).json()
        if "chatters" in users_json:
            new_users = {user: {"rank": rank} for rank, userlist in users_json["chatters"].items() for user in userlist}
            for user, data in new_users.items():
                if user not in self.users:
                    self.users[user] = data
                    self.on_join(user)
            for user, data in dict(self.users).items():
                if user not in new_users:
                    del self.users[user]
                    self.on_leave(user)

    def start(self):
        self.socket = socket.socket()
        self.socket.connect((self.cfg.host, self.cfg.port))
        self.socket.send("PASS {}\r\n".format(self.cfg.password).encode("utf-8"))
        self.socket.send("NICK {}\r\n".format(self.cfg.nick).encode("utf-8"))
        self.socket.send("JOIN {}\r\n".format(self.cfg.channel).encode("utf-8"))

        self.scheduler = BackgroundScheduler()
        self.job_check_twitch = self.scheduler.add_job(self._check_twitch, "interval", minutes=1)
        self.scheduler.start()

        threading.Thread(target=self._check_irc).start()
        self._check_twitch()

    def stop(self):
        self.job_check_twitch.remove()

        self.stopping = True

        self.socket.send("QUIT\r\n".encode("utf-8"))
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
