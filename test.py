import os
import platform


def play_alert_sound():
    """Play an alert sound based on the operating system."""
    try:
        system = platform.system().lower()
        if system == "darwin":  # macOS
            os.system("afplay /System/Library/Sounds/Glass.aiff")
        elif system == "linux":
            os.system("paplay /usr/share/sounds/alsa/Front_Left.wav")
        elif system == "windows":
            import winsound
            winsound.Beep(5000, 1000)  # 1000Hz for 500ms
        else:
            # Fallback: print bell character
            print("\a")
    except Exception as e:
        # Fallback: print bell character
        print("\a")

play_alert_sound()  