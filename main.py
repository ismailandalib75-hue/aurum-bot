# AURUM AI Bot

class AurumAI:
    def __init__(self):
        self.name = 'AURUM AI'

    def greet(self):
        return f'Hello, I am {self.name}!'

if __name__ == '__main__':
    bot = AurumAI()
    print(bot.greet())
