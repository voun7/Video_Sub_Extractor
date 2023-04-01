import subprocess
from tempfile import gettempdir
from typing import Callable, Union


class Sound:
    Default = "ms-winsoundevent:Notification.Default"
    IM = "ms-winsoundevent:Notification.IM"
    Mail = "ms-winsoundevent:Notification.Mail"
    Reminder = "ms-winsoundevent:Notification.Reminder"
    SMS = "ms-winsoundevent:Notification.SMS"
    LoopingAlarm = "ms-winsoundevent:Notification.Looping.Alarm"
    LoopingAlarm2 = "ms-winsoundevent:Notification.Looping.Alarm2"
    LoopingAlarm3 = "ms-winsoundevent:Notification.Looping.Alarm3"
    LoopingAlarm4 = "ms-winsoundevent:Notification.Looping.Alarm4"
    LoopingAlarm6 = "ms-winsoundevent:Notification.Looping.Alarm6"
    LoopingAlarm8 = "ms-winsoundevent:Notification.Looping.Alarm8"
    LoopingAlarm9 = "ms-winsoundevent:Notification.Looping.Alarm9"
    LoopingAlarm10 = "ms-winsoundevent:Notification.Looping.Alarm10"
    LoopingCall = "ms-winsoundevent:Notification.Looping.Call"
    LoopingCall2 = "ms-winsoundevent:Notification.Looping.Call2"
    LoopingCall3 = "ms-winsoundevent:Notification.Looping.Call3"
    LoopingCall4 = "ms-winsoundevent:Notification.Looping.Call4"
    LoopingCall5 = "ms-winsoundevent:Notification.Looping.Call5"
    LoopingCall6 = "ms-winsoundevent:Notification.Looping.Call6"
    LoopingCall7 = "ms-winsoundevent:Notification.Looping.Call7"
    LoopingCall8 = "ms-winsoundevent:Notification.Looping.Call8"
    LoopingCall9 = "ms-winsoundevent:Notification.Looping.Call9"
    LoopingCall10 = "ms-winsoundevent:Notification.Looping.Call10"
    Silent = "silent"


TEMPLATE = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$Template = @"
<toast {launch} duration="{duration}">
    <visual>
        <binding template="ToastImageAndText02">
            <image id="1" src="{icon}" />
            <text id="1"><![CDATA[{title}]]></text>
            <text id="2"><![CDATA[{msg}]]></text>
        </binding>
    </visual>
    <actions>
        {actions}
    </actions>
    {audio}
</toast>
"@

$SerializedXml = New-Object Windows.Data.Xml.Dom.XmlDocument
$SerializedXml.LoadXml($Template)

$Toast = [Windows.UI.Notifications.ToastNotification]::new($SerializedXml)
$Toast.Tag = "{tag}"
$Toast.Group = "{group}"

$Notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app_id}")
$Notifier.Show($Toast);
"""

tempdir = gettempdir()


def _run_ps(*, file='', command=''):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass"]
    if file and command:
        raise ValueError
    elif file:
        cmd.extend(["-file", file])
    elif command:
        cmd.extend(['-Command', command])
    else:
        raise ValueError

    subprocess.Popen(
        cmd,
        # stdin, stdout, and stderr have to be defined here, because windows tries to duplicate these if not null
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,  # set to null because we don't need the output :)
        stderr=subprocess.DEVNULL,
        startupinfo=si
    )


class Notification(object):
    def __init__(self,
                 app_id: str,
                 title: str,
                 msg: str = "",
                 icon: str = "",
                 duration: str = 'short',
                 launch: str = ''):
        """
        Construct a new notification

        Args:
            app_id: your app name, make it readable to your user. It can contain spaces, however special characters
                    (eg. é) are not supported.
            title: The heading of the toast.
            msg: The content/message of the toast.
            icon: An optional path to an image to display on the left of the title & message.
                  Make sure the path is absolute.
            duration: How long the toast should show up for (short/long), default is short.
            launch: The url or callback to launch (invoked when the user clicks the notification)

        Notes:
            If you want to pass a callback to `launch` parameter,
            please use `create_notification` from `Notifier` object

        Raises:
            ValueError: If the duration specified is not short or long
        """

        self.app_id = app_id
        self.title = title
        self.msg = msg
        self.icon = icon
        self.duration = duration
        self.launch = launch
        self.audio = Sound.Silent
        self.tag = self.title
        self.group = self.app_id
        self.actions = []
        self.script = ""
        if duration not in ("short", "long"):
            raise ValueError("Duration is not 'short' or 'long'")

    def set_audio(self, sound: Sound, loop: bool):
        """
        Set the audio for the notification

        Args:
            sound: The audio to play when the notification is showing. Choose one from `winotify.audio` module,
                   (eg. audio.Default). The default for all notification is silent.
            loop: If True, the audio will play indefinitely until user click or dismis the notification.

        """

        self.audio = '<audio src="{}" loop="{}" />'.format(sound, str(loop).lower())

    def add_actions(self, label: str, launch: Union[str, Callable] = ""):
        """
        Add buttons to the notification. Each notification can have 5 buttons max.

        Args:
            label: The label of the button
            launch: The url to launch when clicking the button, 'file:///' protocol is allowed. Or a registered
                    callback function

        Returns: None

        Notes:
            Register a callback function using `Notifier.register_callback()` decorator before passing it here

        Raises:
              ValueError: If the callback function is not registered
        """

        if callable(launch):
            if hasattr(launch, 'url'):
                url = launch.url
            else:
                raise ValueError(f"{launch} is not registered")
        else:
            url = launch

        xml = '<action activationType="protocol" content="{label}" arguments="{link}" />'
        if len(self.actions) < 5:
            self.actions.append(xml.format(label=label, link=url))

    def build(self):
        """
        This method is deprecated, call `Notification.show()` directly instead.

        Warnings:
            DeprecationWarning

        """
        import warnings
        warnings.warn("build method is deprecated, call show directly instead", DeprecationWarning)
        return self

    def show(self):
        """
        Show the toast
        """
        if self.actions:
            self.actions = '\n'.join(self.actions)
        else:
            self.actions = ''

        if self.audio == Sound.Silent:
            self.audio = '<audio silent="true" />'

        if self.launch:
            self.launch = 'activationType="protocol" launch="{}"'.format(self.launch)

        self.script = TEMPLATE.format(**self.__dict__)

        _run_ps(command=self.script)


if __name__ == '__main__':
    toast = Notification(
        app_id="Test id",
        title="test title",
        msg="hey toast"
    )
    # toast.set_audio(Default, loop=True)
    toast.show()
