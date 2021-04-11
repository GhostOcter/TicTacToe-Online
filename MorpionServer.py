import random
import select  # to know if a client has sent data to the server
import socket
import threading


class MorpionServer:
    """
    A server to handle to login, the online morpion and also possibles promblems from 
    the client.
    Protocol:
    ------------------------------------- LOGIN -------------------------------------
        -> Sent:
            -------------------------------------
            LOGIN_ACCEPTED:victories,defeats 
            A client is accpeted via the a good 
            login or a registering.
            -------------------------------------
            LOGIN_REFUSED
            A client try to connect to the server
            but with an invalid login.
            -------------------------------------
        -> Received:
            -------------------------------------
            LOGIN_DEMAND:username,password
            A client try to connect to the server.
            -------------------------------------
    ------------------------------------- MATCHMAKING -------------------------------------
        -> Sent:
            -------------------------------------
            GAME_ACCEPTED:enemy_username,victories,defeats,character
            The server has found an other client.
            A game start.
            -------------------------------------
            GAME_REFUSED
            The server hasen't found any other
            client.
            -------------------------------------
            GAME_CANCELED
            Tell the wait other player thread of the
            client, he must stop.
        -> Received:
            -------------------------------------
            GAME_DEMAND:username
            A client want to play with an other 
            client online
            -------------------------------------
            GAME_CANCELED:username
            A client don't longer want to play online.
            -------------------------------------
    ------------------------------------- ONLINE GAME -------------------------------------
        In this case, the server is just an intermediary.
        The logic is handle by the clients thereself.
        -> Sent & Received:
            -------------------------------------
            NEW_BOX_FILLED:box_index
            A client has played. The box where
            he played is received + sent to the 
            other client
        -> Sent:
            -------------------------------------
            DISCONNECTED_PROBLEM
            This is sent when a the other player
            send  a LOGOUT during the game.
            -------------------------------------

        -> Received:
            -------------------------------------
            GAME_NOT_FINISHED
            The game isn't finished
            -------------------------------------
            GAME_WINNER
            The game is finished and the client
            which emit this message is the winner.
            -------------------------------------
    ------------------------------------- LOGOUT -------------------------------------
        -> Received:
            -------------------------------------
            LOGOUT:username
            Close the socket of the client named
            username.
            -------------------------------------
    """

    def __init__(self):
        self.server_socket = socket.socket()
        self.address = MorpionServer.get_custom_server_address()
        self.server_socket.bind((self.address["ip"], self.address["port"]))
        self.registered_clients = self.get_clients_accounts()
        self.connected_clients = []
        self.online_game_clients = []
        self.game_threads = []
        self.run()

    @staticmethod
    def get_custom_server_address():
        """
        Read the file server_address.config to setting
        the server.
        File format:
            one line -> ip,port
        """
        try:
            with open("server_address.config", "r") as f:
                # getting settings
                datas = [line.rstrip("\n\r").split(":") for line in f.readlines()]
                # transforming the list in a dictionary and casting the port in an integer
                datas = {data[0]:data[1] for data in datas}
                datas["port"] = int(datas["port"])
                return datas    
        except FileNotFoundError:   
            with open("server_address.config", "a") as f:
                f.writelines(["ip:localhost\n", "port:65535"])
            return({"ip":"localhost", "port":65530})
    
    def get_clients_accounts(self):
        """
        Parse the file clients_accounts.txt to extract the data of clients
        File format :
            one line -> username,password,victories,defeats
        """
        try:
            with open("clients_accounts.txt", "r") as f:
                accounts = f.readlines()
                clients = []
                for account in accounts:
                    account_data = account.rstrip("\n\r").split(",")
                    clients.append(
                        {"username": account_data[0], "password": account_data[1], "victories": int(account_data[2]), "defeats":int(account_data[3])}
                    )
                return clients
        except:
            # create the file
            open("clients_accounts.txt", "a").close()        
            return []

    def update_clients_accounts(self):
        """
        Write the datas of clients in the file clients_accounts.txt
        File format :
            one line -> username,password,victories,defeats
        """
        # transforming the registered clients in the file's format
        file_lines = [f"{client['username']},{client['password']},{client['victories']},{client['defeats']}\n" for client in self.registered_clients]
        with open("clients_accounts.txt", "w") as f:
            f.writelines(file_lines)
            
    def login_or_register_client(self, client_sock, client_addr, username, password):
        """
        Login or register a client in the currents connected clients
        """
        # TODO: ADD SECURITY
        found_client = False
        # login client
        for client in self.registered_clients:
            if client["username"] == username:
                if client["password"] == password:
                    print(f"[+] Logging client {username}...")
                    client_copy = client.copy()
                    client_copy.update({"socket":client_sock, "address" : client_addr})
                    self.connected_clients.append(client_copy)
                    client_sock.send(b"LOGIN_ACCEPTED:" + f"{client['victories']},{client['defeats']}".encode())
                    found_client = True
                else:
                    print(f"[+] Refusing to login {username} : invalid password.")
                    client_sock.send(b"LOGIN_REFUSED")
                    return
        # reguster client
        if not found_client:
            print(f"[+] Registering client {username}...")
            client = {"username": username, "password": password, "victories": 0, "defeats":0}
            self.registered_clients.append(client)
            client_copy = client.copy()
            client_copy.update({"socket":client_sock, "address" : client_addr})
            self.connected_clients.append(client_copy)
            client_sock.send(b"LOGIN_ACCEPTED:0,0")
            self.update_clients_accounts()

    def create_game(self, cross_account, circle_account):    
        """
        Handle the role of intermediary between the
        two players during the game.
        """
        game_finished = False
        thread_name = self.game_threads[-1]
        while not game_finished:
            # ----------------------- CROSS TURN -----------------------
            # get the position of the new box filled and send this to the circle
            main_request_cross = cross_account["socket"].recv(2048).decode().rstrip("\r\n").split(":")
            print(f"\t[-]{thread_name}, {cross_account['username']} -> \t{main_request_cross}")
            # verify if cross doesn't exit the game
            if main_request_cross[0] == "NEW_BOX_FILLED":
                circle_account["socket"].send(":".join(main_request_cross).encode())
            else:   # LOGOUT
                self.connected_clients.append(circle_account)
                circle_account["socket"].send(b"DISCONNECTED_PROBLEM")
                self.close_session(main_request_cross[1])
                return
            # verify if the game is finished and cross is the winner
            game_state = cross_account["socket"].recv(2048).decode().rstrip("\r\n").split(":")
            if game_state[0] == "GAME_WINNER":
                print(f"[+] Winner {cross_account['username']} / Looser {circle_account['username']}")
                cross_account["victories"] += 1
                circle_account["defeats"] += 1
                self.connected_clients += [cross_account, circle_account]
                return
            elif game_state[0] == "LOGOUT":
                self.connected_clients.append(circle_account)
                circle_account["socket"].send(b"DISCONNECTED_PROBLEM")
                self.close_session(game_state[1])
                return
            
            #----------------------- ENEMY TURN -----------------------
            # get the position of the new box filled and send this to the cirlce
            main_request_circle = circle_account["socket"].recv(2048).decode().rstrip("\r\n").split(":")
            print(f"\t[-]{thread_name}, {circle_account['username']} -> \t{main_request_circle}")
            if main_request_circle[0] == "NEW_BOX_FILLED":
                cross_account["socket"].send(":".join(main_request_circle).encode())
            else:   # LOGOUT
                self.connected_clients.append(cross_account)
                cross_account["socket"].send(b"DISCONNECTED_PROBLEM")
                self.close_session(main_request_circle[1])
                return
            # verify if the game is finished and cirlce is the winner
            game_state = circle_account["socket"].recv(2048).decode().rstrip("\r\n").split(":")
            if game_state[0] == "GAME_WINNER":
                print(f"[+] Winner {circle_account['username']} / Looser {cross_account['username']}")                
                cross_account["victories"] += 1
                circle_account["defeats"] += 1
                self.connected_clients += [cross_account, circle_account]
                return
            elif game_state[0] == "LOGOUT":
                self.connected_clients.append(cross_account)
                cross_account["socket"].send(b"DISCONNECTED_PROBLEM")
                self.close_session(game_state[1])
                return

    def handler_clients(self):
        while self.running:
            if len(self.connected_clients) > 0:
                sockets_ready = select.select([client["socket"] for client in self.connected_clients], [], [], 2)[0]
                for socket_ready in sockets_ready:
                    request = socket_ready.recv(2048).decode("utf-8").rstrip("\r\n").split(":")
                    print(f"([+] A request has been received :\t {request[0]}.)")
                    if request[0] == "GAME_DEMAND":
                        if len(self.online_game_clients) > 0 :       
                            enemy_username =  self.online_game_clients.pop(random.randint(0, len(self.online_game_clients) - 1))
                            print(f"[+] Creating game for clients :\n\t {request[1]} /vs/ {enemy_username}")
                            circle_account = None
                            requester_username = request[1]
                            cross_account = None
                            for client in self.connected_clients:
                                if client["username"] == enemy_username:
                                    circle_account = client
                                elif client["username"] == requester_username:
                                    cross_account = client
                            self.connected_clients.remove(circle_account)
                            self.connected_clients.remove(cross_account)
                            self.game_threads.append(threading.Thread(None, self.create_game, args=(cross_account, circle_account)))
                            self.game_threads[-1].start()
                            socket_ready.send(
                                f"GAME_ACCEPTED:{enemy_username},{circle_account['victories']},{circle_account['defeats']},O".encode()
                                )
                            circle_account["socket"].send(
                                f"GAME_ACCEPTED:{requester_username},{cross_account['victories']},{cross_account['defeats']},X".encode()
                                )
                        else:
                            self.online_game_clients.append(request[1])
                            socket_ready.send(b"GAME_REFUSED")
                            print(f"[+] Adding client to the current online game clients : \n\t {self.online_game_clients}")
                    elif request[0] == "GAME_CANCELED":
                        print(f"[+] The client {request[1]} has canceled his game demand.")
                        self.online_game_clients.remove(request[1])
                        for client in self.connected_clients:
                            if client["username"] == request[1]:
                                # tell the wait thread to stop him
                                client["socket"].send(b"GAME_CANCELED")
                    elif request[0] == "LOGOUT":
                        self.close_session(request[1])
        
    def close_session(self, username):
        for client in self.connected_clients:
            if client["username"] == username:
                for registered_client in self.registered_clients:
                    if registered_client["username"] == username:
                        print(f"[+] Close session of {username}.")
                        registered_client["victories"] = client["victories"]
                        registered_client["defeats"] = client["defeats"]
                        client["socket"].close()
                        self.connected_clients.remove(client)
                        self.update_clients_accounts()
                        return

    def run(self):
        """
        Server's mainloop, handle new connections.
        """
        self.running = True
        print("[+] Wait for connections...")
        self.server_socket.listen(10)               # 10 clients 
        self.handler_clients_thread = threading.Thread(None ,self.handler_clients)
        self.handler_clients_thread.start()
        while self.running:
            # a new client connect to the server
            client_sock, client_addr = self.server_socket.accept()
            login_data = client_sock.recv(2048).decode("utf-8").rstrip("\n\r")
            # recv the LOGIN_DEMAND from the client
            username, password = login_data.split(":")[1].split(",")
            print(f"[+] Recive a connection from the client {username}.")
            self.login_or_register_client(client_sock, client_addr, username, password)
            

if __name__ == "__main__":
    MorpionServer()
