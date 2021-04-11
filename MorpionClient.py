import random
import socket
import threading
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle
from kivy.properties import (BooleanProperty, NumericProperty, ObjectProperty,
                             StringProperty)
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

from MorpionServer import MorpionServer

from kivy.config import Config

# to avoid multitouch emulation
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

#--------------------------- GLOBALS VARIABLES ---------------------------
black         = get_color_from_hex("#0B0C10")
light_black   = get_color_from_hex("#1F2833")
grey          = get_color_from_hex("#C5C6C7")
light_blue    = get_color_from_hex("#66FCF1")
dark_blue     = get_color_from_hex("#45A29E")
white         = 1, 1, 1, 1

#--------------------------- LOGIN PART ---------------------------
class LoginButton(Button):
        def on_press(self):
            super().on_press()
            # Updating the texture
            self.text = "Logging..."
            with self.canvas:
                Color(*black)
                Line(width = 2, rounded_rectangle = (self.x, self.y, self.width, self.height, 20, 100))
            # Logging the user
            Clock.schedule_once(self.register_or_login, 0.5)
        
        def on_release(self):
            super().on_release()
            with self.canvas:
                Color(*grey)
                Line(width = 2, rounded_rectangle = (self.x, self.y, self.width, self.height, 20, 100))
                Color(light_black[0], light_black[1], light_black[2], 0.2)
                Line(width = 1, rounded_rectangle = (self.x, self.y, self.width, self.height, 20, 100))   
                
        def register_or_login(self, *_) -> str:
            #TODO : ADD VERIFICATION FOR THE USERNAME AND THE PASSWORD 
            login_screen : Screen
            for widget in self.walk_reverse():
                if isinstance(widget, Screen) and widget.name == "LoginScreen":
                    login_screen = widget
            username = login_screen.username.text
            password = login_screen.password.text
            morpion_manager : ScreenManager = login_screen.manager
            morpion_manager.server_socket = socket.socket()
            address = MorpionServer.get_custom_server_address()
            try:
                morpion_manager.server_socket.connect((address["ip"], address["port"]))
            except:
                morpion_manager.offline = True
                self.text = "Offline !"
                login_screen = morpion_manager.current_screen
                morpion_manager.add_widget(MenuScreen())
                morpion_manager.current = "MenuScreen"
                morpion_manager.account = {"username": username, "victories": 0, "defeats": 0}
                morpion_manager.remove_widget(login_screen)
                return
            morpion_manager.server_socket.send(f"LOGIN_DEMAND:{username},{password}".encode("utf-8"))
            answer = morpion_manager.server_socket.recv(2048).decode("utf-8").split(":")
            if answer[0] == "LOGIN_ACCEPTED":
                self.text = "Logged !"
                data = answer[1].split(",")
                victories, defeats = int(data[0]), int(data[1])
                morpion_manager.account = {"username": username, "victories":victories, "defeats": defeats}
                morpion_manager.add_widget(MenuScreen())
                morpion_manager.current = "MenuScreen"
                for screen in morpion_manager.screens:
                    if screen.name == "LoginScreen":
                        morpion_manager.remove_widget(screen)
            else:
                self.text = "Invalid password !"


class LoginScreen(Screen):
    username = ObjectProperty(None)
    password = ObjectProperty(None)
    def __init__(self, **kwargs):
        super().__init__()
        self.name = "LoginScreen"

#--------------------------- MENU PART ---------------------------
class MenuElement(Button):
    hint_x = NumericProperty(0.5)
    def __init__(self, hint_distance_hover = 0.1, **kwargs):
        super().__init__(**kwargs)
        self.to_hint_x = self.hint_x + hint_distance_hover
        self.from_hint_x = self.hint_x
        self.can_play_hover_animation = True
        self.hover_animation = Animation(hint_x = self.to_hint_x, duration = 0.5, t = "out_cubic")
        self.unhover_animation = Animation(hint_x = self.from_hint_x, duration = 0.5, t = "out_cubic")
        self.mouse_event = Clock.schedule_interval(self.on_mouse_pos, 1/60)

    def on_mouse_pos(self, event):
        is_mouse_colliding_with_button = self.collide_point(*Window.mouse_pos)
        if is_mouse_colliding_with_button:
            if self.can_play_hover_animation:
                self.can_play_hover_animation = False
                self.can_play_unhover_animation = True
                self.text = "-" + self.text
                self.hover_animation.start(self)
        elif not is_mouse_colliding_with_button and not self.can_play_hover_animation:
            self.can_play_hover_animation = True
            self.can_play_unhover_animation = False
            self.text = self.text.strip("-")
            self.unhover_animation.start(self)


class SubMenuContainer(FloatLayout):
    pass


class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__()
        self.name = "MenuScreen"
        self.sub_menu_containers = dict()
        for id in self.ids:
            if isinstance(self.ids[id], SubMenuContainer):
                self.ids[id].opacity = 0
                self.sub_menu_containers.update({id : self.ids[id]})
                self.ids[id].opacity = 1
                if id != "main_menu":
                    self.ids[id].parent.remove_widget(self.ids[id])
        self.showing_animation = Animation(opacity = 1, duration = 0.5, t = "in_back")
        self.hiding_animation = Animation(opacity = 0, duration = 0.5, t = "out_back")
        self.hiding_animation.bind(on_complete = self.on_hiding_completed)

    def change_sub_menu(self, menu_element):
        self.current_target = menu_element.target
        for parent in menu_element.walk_reverse():
            if isinstance(parent, SubMenuContainer):
                self.hiding_animation.start(parent)
    
    def on_hiding_completed(self, animation, sub_menu_container):
        parent_sub_menu_container = sub_menu_container.parent
        parent_sub_menu_container.remove_widget(sub_menu_container)
        parent_sub_menu_container.add_widget(self.sub_menu_containers[self.current_target])
        self.showing_animation.start(self.sub_menu_containers[self.current_target])

    def go_to_game_screen(self, multiplayer = False, online = False):
            self.manager.add_widget(GameScreen(self.manager,  multiplayer, online))
            self.manager.current = "GameScreen"
            self.manager.remove_widget(self)

# --------------------------- GAME PART ---------------------------
class MorpionBox(Button):
    def is_empty(self):
        if self.text != "O" and self.text != "X":
            return True
        return False

class PlayerInfo(Label):
    pass

class MorpionGrid(GridLayout):
    winner = StringProperty("")
    null_game = BooleanProperty(False)
    disconnected_problem = BooleanProperty(False)
    def __init__(self, server_socket, **kwargs):    
        super().__init__(**kwargs)
        self.global_font = "Fonts/Hack-Regular.ttf"
        self.counter = 0
        self.spawn_animation = Animation(color = light_blue, duration = 0.2, t = "out_back")
        self.spawn_animation += Animation(color = dark_blue, duration = 0.2, t = "out_back")
        self.spawn_animation += Animation(color = grey, duration = 0.2, t = "out_back")
        self.grid_animation = Animation(opacity = 1, duration = 0.5, t = "in_back")
        self.opacity = 0
        self.morpion_boxes = list()
        self.server_socket = server_socket
    
    def prepare_online_game(self, enemy_account):
        self.turn = 0 if enemy_account["character"] == "O" else 1
        self.character = "X" if enemy_account["character"] == "O" else "O"
        self.enemy_character = enemy_account["character"]
        self.update = self.mutliplayer_online_update
        self.wait_enemy_thread = threading.Thread(None, self.wait_enemy_action)
        if enemy_account["character"] == "X":
            self.wait_enemy_thread.start()

    def mutliplayer_local_update(self, instance):
        if instance.text == "":
            instance.font_name = self.global_font
            instance.text = "X" if (self.counter % 2) == 0 else "O"
            self.spawn_animation.start(instance)
            self.counter += 1
            self.verify()

    def mutliplayer_online_update(self, instance):
        if instance.text == "" and self.counter % 2 == self.turn:
            instance.font_name = self.global_font
            instance.font_size  = "80sp"
            instance.text = self.character
            self.spawn_animation.start(instance)
            self.counter += 1
            self.server_socket.send(b"NEW_BOX_FILLED:" + str(self.morpion_boxes.index(instance)).encode())
            if not self.verify():
                self.server_socket.send(b"GAME_NOT_FINISHED")
                self.wait_enemy_thread = threading.Thread(None, self.wait_enemy_action)
                self.wait_enemy_thread.start()
            else:
                self.server_socket.send(b"GAME_WINNER")
    
    def wait_enemy_action(self):
        request = self.server_socket.recv(2048).decode("utf-8").split(":")
        if request[0] == "DISCONNECTED_PROBLEM":
            # the other player is disconnected 
            self.disconnected_problem = True
            return
        else:
            self.morpion_boxes[int(request[1])].text = self.enemy_character
        self.counter += 1
        self.verify()

    def verify(self):
        """
        Verify if there is a winner or if the game is null.
        Return True if the game is finished
        """
        # verify if X win
        if self.morpion_boxes[0].text == "X" and self.morpion_boxes[1].text == "X" and self.morpion_boxes[2].text == "X"\
        or self.morpion_boxes[3].text == "X" and self.morpion_boxes[4].text == "X" and self.morpion_boxes[5].text == "X"\
        or self.morpion_boxes[6].text == "X" and self.morpion_boxes[7].text == "X" and self.morpion_boxes[8].text == "X"\
        or self.morpion_boxes[0].text == "X" and self.morpion_boxes[4].text == "X" and self.morpion_boxes[8].text == "X"\
        or self.morpion_boxes[2].text == "X" and self.morpion_boxes[4].text == "X" and self.morpion_boxes[6].text == "X"\
        or self.morpion_boxes[0].text == "X" and self.morpion_boxes[3].text == "X" and self.morpion_boxes[6].text == "X"\
        or self.morpion_boxes[1].text == "X" and self.morpion_boxes[4].text == "X" and self.morpion_boxes[7].text == "X"\
        or self.morpion_boxes[2].text == "X" and self.morpion_boxes[5].text == "X" and self.morpion_boxes[8].text == "X":
            self.winner = "X"
            return True
        # verify if O win
        elif self.morpion_boxes[0].text == "O" and self.morpion_boxes[1].text == "O" and self.morpion_boxes[2].text == "O"\
        or self.morpion_boxes[3].text == "O" and self.morpion_boxes[4].text == "O" and self.morpion_boxes[5].text == "O"\
        or self.morpion_boxes[6].text == "O" and self.morpion_boxes[7].text == "O" and self.morpion_boxes[8].text == "O"\
        or self.morpion_boxes[0].text == "O" and self.morpion_boxes[4].text == "O" and self.morpion_boxes[8].text == "O"\
        or self.morpion_boxes[2].text == "O" and self.morpion_boxes[4].text == "O" and self.morpion_boxes[6].text == "O"\
        or self.morpion_boxes[0].text == "O" and self.morpion_boxes[3].text == "O" and self.morpion_boxes[6].text == "O"\
        or self.morpion_boxes[1].text == "O" and self.morpion_boxes[4].text == "O" and self.morpion_boxes[7].text == "O"\
        or self.morpion_boxes[2].text == "O" and self.morpion_boxes[5].text == "O" and self.morpion_boxes[8].text == "O":
            self.winner = "O"
            return True

        # verify if it is a null game        
        i = 0
        for morpion_box in self.morpion_boxes:
            if morpion_box.text == "":
                break
            else:
                i += 1
            if i == 9:
                self.null_game = True
                return True

class GameScreen(Screen):
    main_container = ObjectProperty()
    def __init__(self, screen_manager, multiplayer, online, **kwargs):
        super().__init__(**kwargs)
        self.name = "GameScreen"
        self.sm = screen_manager
        self.morpion_grid = MorpionGrid(screen_manager.server_socket)
        for child in self.morpion_grid.walk():
            if isinstance(child, MorpionBox):
                self.morpion_grid.morpion_boxes.append(child)
        self.morpion_grid.bind(winner = self.on_winner)
        self.morpion_grid.bind(null_game = self.on_null_game)
        self.morpion_grid.bind(disconnected_problem = self.on_disconnected_problem)
        self.settings(multiplayer, online)

    def settings(self, multiplayer, online):
        if multiplayer and not online:
            self.multiplayer_online = False
            self.morpion_grid.update = self.morpion_grid.mutliplayer_local_update
            self.main_container.add_widget(self.morpion_grid)
            self.morpion_grid.grid_animation.start(self.morpion_grid)
        elif self.sm.offline != True:            
            self.server_socket = self.sm.server_socket
            # Init the game
            try:
                self.server_socket.send(b"GAME_DEMAND:" + self.sm.account["username"].encode())       
                answer = self.server_socket.recv(2048).decode("utf-8").rstrip("\r\n").split(":")
                
                if answer[0] == "GAME_ACCEPTED":
                    data = answer[1].split(",")
                    enemy_account = {"username": data[0], "victories": data[1], "defeats": data[2], "character":data[3]}
                    self.enemy_username = data[0]
                    self.add_players_info(enemy_account)
                    self.morpion_grid.prepare_online_game(enemy_account)
                    self.main_container.add_widget(self.morpion_grid)
                    self.morpion_grid.grid_animation.start(self.morpion_grid)
                    self.multiplayer_online = True
                else:       # GAME_REFUSED
                    self.info = InfoPopup(text = "There isn't other player. Wait please... Click anywhere if you want to return to the menu.")
                    self.info.bind(on_touch_down = self.cancel_game_demand)
                    self.add_widget(self.info)
                    self.wait_thread = threading.Thread(None, self.wait_ohter_player)
                    self.wait_thread.start()
    
            except socket.error as e:
                print(e)
                self.server_socket = None
                error_info = InfoPopup(text = "You are currently offline or the server isn't responding.")
                error_info.popup_animation.bind(on_complete = lambda *_: self.go_to_menu())
                self.add_widget(error_info)
        else:
            error_info = InfoPopup(text = "You have been loggged offline, so you can't play online.")
            error_info.popup_animation.bind(on_complete = lambda *_: self.go_to_menu())
            self.add_widget(error_info)
    
    def cancel_game_demand(self, *_):
        self.server_socket.send(f"GAME_CANCELED:{self.sm.account['username']}".encode())
        self.go_to_menu()

    def add_players_info(self, enemy_account):
        player_label = PlayerInfo(
            text = f"Username :  {self.sm.account['username']}\nVictories : {self.sm.account['victories']}\nDefeats :   {self.sm.account['defeats']}", 
            pos_hint = {"center_x": 0.5, "bottom" : 1},
            )

        enemy_label = PlayerInfo(
            text = f"Username :  {enemy_account['username']}\nVictories : {enemy_account['victories']}\nDefeats :   {enemy_account['defeats']}",
            pos_hint = {"center_x": 0.5, "top": 1}
            )
            
        self.main_container.add_widget(player_label)
        self.main_container.add_widget(enemy_label)

    def wait_ohter_player(self):
        answer = self.server_socket.recv(2048).decode("utf-8").rstrip("\r\n").split(":")
        if answer[0] == "GAME_ACCEPTED":
            data = answer[1].split(",")
            enemy_account = {"username": data[0], "victories": data[1], "defeats": data[2], "character":data[3]}
            self.enemy_username = data[0]
            self.remove_widget(self.info)
            self.morpion_grid.prepare_online_game(enemy_account)
            self.add_players_info(enemy_account)
            self.main_container.add_widget(self.morpion_grid)
            self.morpion_grid.grid_animation.start(self.morpion_grid)
            self.multiplayer_online = True
        else:   # GAME_CANCELED
            return

    def on_winner(self, _, value):
        if not self.multiplayer_online:
            winner = value 
        else:
            winner = self.sm.account["username"] if value == self.morpion_grid.character else self.enemy_username

        win_label = Label(text = f"[WINNER:{winner}!]", font_name = "Fonts/KGDefyingGravityBounce.ttf", font_size = "100sp",
                        pos_hint = {"center_x": 0.5, "top" : 0}, size_hint = (0.5, 0.5))
        self.add_widget(win_label)
        fade_animation = Animation(opacity = 0.2, duration = 1, t = "in_back") + Animation(opacity = 0, duration = 2, t = "out_back")
        fade_animation.bind(on_complete = self.go_to_menu)
        translate_animation = Animation(pos_hint = {"center_x": 0.5, "top" : 1}, duration = 1, t = "out_back")
        fade_animation.start(self.main_container)
        translate_animation.start(win_label)
        if self.multiplayer_online and self.morpion_grid.character == value:
            self.sm.account["victories"] += 1
        else:
            self.sm.account["defeats"] += 1

    def on_null_game(self, *_):
        game_over_label = Label(text = "(Game Over)", font_name = "Fonts/KGALittleSwag.ttf", font_size = "100sp",
                        pos_hint = {"center_x": 0.5, "top" : 0}, size_hint = (0.5, 0.5))
        self.add_widget(game_over_label)
        fade_animation = Animation(opacity = 0.2, duration = 1, t = "in_back") + Animation(opacity = 0, duration = 2, t = "out_back")
        fade_animation.bind(on_complete = self.go_to_menu)
        translate_animation = Animation(pos_hint = {"center_x": 0.5, "top" : 1}, duration = 1, t = "out_back")
        fade_animation.start(self.main_container)
        translate_animation.start(game_over_label)
    
    def on_disconnected_problem(self, *_):
        self.remove_widget(self.main_container)
        problem_info = InfoPopup(text = "The other player has exited the game.")
        problem_info.popup_animation.bind(on_complete = self.go_to_menu)
        self.add_widget(problem_info)
    
    def go_to_menu(self, *_):
        morpion_manager = self.parent
        morpion_manager.add_widget(MenuScreen())
        morpion_manager.current = "MenuScreen"
        morpion_manager.remove_widget(self)

class InfoPopup(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.popup_animation = Animation(pos_hint = {"top": 0.5}, duration = 1.0, t = "linear") + Animation(pos_hint = {"top ": 0.6}, duration = 3.0, t = "linear")
        self.popup_animation.start(self)

# --------------------------- GOBAL APP ---------------------------

class MorpionManager(ScreenManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.account : list
        self.offline = False
        self.server_socket : socket.socket
        self.transition = FadeTransition()
        self.add_widget(LoginScreen())
        self.current = "LoginScreen"

class MorpionApp(App):
    def build(self):
        self.morpion_manager = MorpionManager()
        return self.morpion_manager
    
    def on_stop(self):
        if not self.morpion_manager.offline:
            self.morpion_manager.server_socket.send(f"LOGOUT:{self.morpion_manager.account['username']}".encode())


if __name__ == "__main__":
    MorpionApp().run()
    