from terminaltexteffects.effects import Thunderstorm

effect = Thunderstorm("""
I know you're somewhere out there, somewhere far away
I want you back, I want you back
My neighbors think I'm crazy, but they don't understand
You're all I had, you're all I had
At night, when the stars light up my room
I sit by myself
Talking to the moon
Tryna get to you
In hopes you're on the other side talking to me too
Or am I a fool who sits alone talking to the moon?
Oh
I'm feelin' like I'm famous, the talk of the town
They say I've gone mad, yeah, I've gone mad
But they don't know what I know, 'cause when the sun goes down
Someone's talking back, yeah, they're talking back, oh
At night, when the stars light up my room
I sit by myself
Talking to the moon
Tryna get to you
In hopes you're on the other side talking to me too
Or am I a fool who sits alone talking to the moon?
Ah, ah, ah
Do you ever hear me calling?
(Ah) oh-oh-oh (ah), oh-oh-oh (ah)
'Cause every night I'm talking to the moon
Still tryna get to you
In hopes you're on the other side talking to me too
Or am I a fool who sits alone talking to the moon?
Oh
I know you're somewhere out there, somewhere far away
""")
with effect.terminal_output() as terminal:
    for frame in effect:
        terminal.print(frame)