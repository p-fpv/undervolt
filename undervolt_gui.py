import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import json
import os
import re
import sys

# Файл для хранения профилей
PROFILES_FILE = os.path.expanduser("~/.undervolt_gui_profiles.json")

def ask_password():
    """Показывает диалоговое окно для ввода пароля sudo."""
    temp_root = tk.Tk()
    temp_root.title("Требуются права root")
    temp_root.geometry("300x120")
    temp_root.resizable(False, False)

    # Центрирование окна
    screen_width = temp_root.winfo_screenwidth()
    screen_height = temp_root.winfo_screenheight()
    x = (screen_width - 300) // 2
    y = (screen_height - 120) // 2
    temp_root.geometry(f"+{x}+{y}")

    lbl = tk.Label(temp_root, text="Программа запущена без sudo.\nВведите пароль пользователя:")
    lbl.pack(pady=10)

    pwd_var = tk.StringVar()
    entry = tk.Entry(temp_root, textvariable=pwd_var, show="*", width=25)
    entry.pack(pady=5)
    entry.focus_set()

    def on_ok(event=None):
        temp_root.quit()

    btn = tk.Button(temp_root, text="OK", command=on_ok, width=10)
    btn.pack(pady=5)

    entry.bind('<Return>', on_ok)

    temp_root.mainloop()

    password = pwd_var.get()
    temp_root.destroy()
    return password

class UndervoltGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Undervolt GUI")
        self.root.geometry("800x750")

        # Переменная для имени профиля
        self.profile_name_var = tk.StringVar(value="Default")

        # Переменные для настроек
        self.vars = {
            'core': tk.DoubleVar(value=0.0),
            'cache': tk.DoubleVar(value=0.0),
            'gpu': tk.DoubleVar(value=0.0),
            'uncore': tk.DoubleVar(value=0.0),
            'analogio': tk.DoubleVar(value=0.0),
            'p1_power': tk.DoubleVar(value=0.0),
            'p1_time': tk.DoubleVar(value=0.0),
            'p2_power': tk.DoubleVar(value=0.0),
            'p2_time': tk.DoubleVar(value=0.0),
            'turbo_disable': tk.BooleanVar(value=False)
        }

        self.check_cpu_gen()
        self.create_widgets()
        self.update_profile_list() # Загрузить список профилей в комбобокс

        # Сразу читаем состояние при запуске
        self.read_undervolt()

    def check_cpu_gen(self):
        """Проверяет модель процессора для 11-го поколения Intel."""
        self.is_11th_gen = False
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read()
                if '11th Gen' in content or 'Tiger Lake' in content or 'Rocket Lake' in content:
                    self.is_11th_gen = True
        except Exception:
            pass

    def create_widgets(self):
        # --- Верхняя панель: Управление и Профили ---
        frame_top = ttk.Frame(self.root)
        frame_top.pack(fill="x", padx=10, pady=5)

        # Кнопка Read
        btn_read = ttk.Button(frame_top, text="Обновить (Read)", command=self.read_undervolt)
        btn_read.pack(side="left", padx=5)

        # Сепаратор
        ttk.Separator(frame_top, orient='vertical').pack(side="left", fill="y", padx=10)

        # Управление профилями
        lbl_prof = ttk.Label(frame_top, text="Профиль:")
        lbl_prof.pack(side="left", padx=2)

        self.combo_profiles = ttk.Combobox(frame_top, textvariable=self.profile_name_var, width=20)
        self.combo_profiles.pack(side="left", padx=5)

        btn_load_prof = ttk.Button(frame_top, text="Загрузить", command=self.load_profile)
        btn_load_prof.pack(side="left", padx=2)

        btn_save_prof = ttk.Button(frame_top, text="Сохранить", command=self.save_profile)
        btn_save_prof.pack(side="left", padx=2)

        # --- Панель логов ---
        frame_log = ttk.LabelFrame(self.root, text="Вывод (undervolt --read)")
        frame_log.pack(fill="both", expand=False, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(frame_log, height=8, state='disabled')
        self.log_area.pack(fill="both", padx=5, pady=5)

        # --- Средняя панель: Вольтаж ---
        frame_volts = ttk.LabelFrame(self.root, text="Смещение напряжения (mV)")
        frame_volts.pack(fill="x", padx=10, pady=5)

        grid_frame = ttk.Frame(frame_volts)
        grid_frame.pack(fill="x", padx=5, pady=5)

        labels = ['Core', 'Cache', 'GPU', 'Uncore', 'AnalogIO']
        keys = ['core', 'cache', 'gpu', 'uncore', 'analogio']

        for i, (label, key) in enumerate(zip(labels, keys)):
            ttk.Label(grid_frame, text=f"{label}:").grid(row=i//2, column=(i%2)*2, padx=5, pady=2, sticky="e")
            entry = ttk.Entry(grid_frame, textvariable=self.vars[key], width=10)
            entry.grid(row=i//2, column=(i%2)*2+1, padx=5, pady=2)

            if self.is_11th_gen and key != 'core':
                entry.config(state='disabled')

        if self.is_11th_gen:
            warn_lbl = ttk.Label(frame_volts, text="ВНИМАНИЕ: Обнаружено 11-е поколение Intel.\nДоступен только Core.", foreground="red")
            warn_lbl.pack(pady=5)

        # --- Панель: Power Limits ---
        frame_power = ttk.LabelFrame(self.root, text="Power Limits (PL1 / PL2)")
        frame_power.pack(fill="x", padx=10, pady=5)

        p_frame = ttk.Frame(frame_power)
        p_frame.pack(fill="x", padx=5, pady=5)

        # PL1 (Long)
        ttk.Label(p_frame, text="PL1 (Long):").grid(row=0, column=0, padx=5, sticky="e")
        ttk.Entry(p_frame, textvariable=self.vars['p1_power'], width=8).grid(row=0, column=1, padx=2)
        ttk.Label(p_frame, text="W").grid(row=0, column=2, padx=2)
        ttk.Entry(p_frame, textvariable=self.vars['p1_time'], width=8).grid(row=0, column=3, padx=2)
        ttk.Label(p_frame, text="sec").grid(row=0, column=4, padx=2)

        # PL2 (Short)
        ttk.Label(p_frame, text="PL2 (Short):").grid(row=1, column=0, padx=5, sticky="e")
        ttk.Entry(p_frame, textvariable=self.vars['p2_power'], width=8).grid(row=1, column=1, padx=2)
        ttk.Label(p_frame, text="W").grid(row=1, column=2, padx=2)
        ttk.Entry(p_frame, textvariable=self.vars['p2_time'], width=8).grid(row=1, column=3, padx=2)
        ttk.Label(p_frame, text="sec").grid(row=1, column=4, padx=2)

        # --- Панель: Прочее ---
        frame_misc = ttk.LabelFrame(self.root, text="Прочее")
        frame_misc.pack(fill="x", padx=10, pady=5)
        ttk.Checkbutton(frame_misc, text="Отключить Turbo Boost", variable=self.vars['turbo_disable']).pack(anchor="w", padx=10, pady=5)

        # --- Кнопка Применить ---
        # Добавим её отдельно внизу, так как нижнюю панель убрали, но кнопка нужна
        frame_apply = ttk.Frame(self.root)
        frame_apply.pack(fill="x", padx=10, pady=15)

        ttk.Button(frame_apply, text="ПРИМЕНИТЬ НАСТРОЙКИ", command=self.apply_settings).pack(fill="x", ipady=10)

        ttk.Label(self.root, text="Используйте на свой риск!", foreground="gray").pack(side="bottom", pady=5)

    def update_profile_list(self):
        """Читает файл профилей и обновляет выпадающий список."""
        profiles = []
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, 'r') as f:
                    data = json.load(f)
                    profiles = list(data.keys())
            except Exception:
                pass

        self.combo_profiles['values'] = profiles
        if profiles and self.profile_name_var.get() not in profiles:
            self.profile_name_var.set(profiles[0])

    def parse_read_output(self, text):
        """Парсит вывод undervolt --read, отбрасывает дробную часть и обновляет self.vars"""
        lines = text.split('\n')
        for line in lines:
            match = re.search(r'(\w+):\s*([\-\d\.]+)\s*mV', line)
            if match:
                key = match.group(1).lower()
                val = int(float(match.group(2)))
                if key in self.vars:
                    self.vars[key].set(val)

            if "turbo:" in line:
                is_enabled = "enabled" in line
                self.vars['turbo_disable'].set(not is_enabled)

            match_power = re.search(r'powerlimit:\s*([\d\.]+)W.*short:\s*([\d\.]+)s.*\/\s*([\d\.]+)W.*long:\s*([\d\.]+)s', line)
            if match_power:
                self.vars['p2_power'].set(int(float(match_power.group(1))))
                self.vars['p2_time'].set(int(float(match_power.group(2))))
                self.vars['p1_power'].set(int(float(match_power.group(3))))
                self.vars['p1_time'].set(int(float(match_power.group(4))))

    def read_undervolt(self):
        """Выполняет undervolt --read и заполняет поля."""
        try:
            result = subprocess.run(['undervolt', '--read'], capture_output=True, text=True, check=True)

            self.log_area.config(state='normal')
            self.log_area.delete(1.0, tk.END)
            self.log_area.insert(tk.END, result.stdout)
            self.log_area.config(state='disabled')

            self.parse_read_output(result.stdout)

        except FileNotFoundError:
            messagebox.showerror("Ошибка", "Программа 'undervolt' не найдена.")
        except subprocess.CalledProcessError as e:
            self.log_area.config(state='normal')
            self.log_area.delete(1.0, tk.END)
            self.log_area.insert(tk.END, f"Ошибка:\n{e.stderr}")
            self.log_area.config(state='disabled')

    def apply_settings(self):
        """Собирает команду и применяет настройки."""
        cmd = ['undervolt', '-v']

        def get_int_val(var):
            try:
                return int(var.get())
            except:
                return 0

        c_val = get_int_val(self.vars['core'])
        if c_val != 0: cmd.append(f"--core {c_val}")

        if not self.is_11th_gen:
            if get_int_val(self.vars['cache']) != 0: cmd.append(f"--cache {get_int_val(self.vars['cache'])}")
            if get_int_val(self.vars['gpu']) != 0: cmd.append(f"--gpu {get_int_val(self.vars['gpu'])}")
            if get_int_val(self.vars['uncore']) != 0: cmd.append(f"--uncore {get_int_val(self.vars['uncore'])}")
            if get_int_val(self.vars['analogio']) != 0: cmd.append(f"--analogio {get_int_val(self.vars['analogio'])}")

        p1_p = get_int_val(self.vars['p1_power'])
        p1_t = get_int_val(self.vars['p1_time'])
        if p1_p > 0 and p1_t > 0:
            cmd.append(f"-p1 {p1_p} {p1_t}")

        p2_p = get_int_val(self.vars['p2_power'])
        p2_t = get_int_val(self.vars['p2_time'])
        if p2_p > 0 and p2_t > 0:
            cmd.append(f"-p2 {p2_p} {p2_t}")

        val = 1 if self.vars['turbo_disable'].get() else 0
        cmd.append(f"--turbo {val}")

        try:
            final_cmd = []
            for c in cmd:
                parts = c.split()
                final_cmd.extend(parts)

            result = subprocess.run(final_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                messagebox.showinfo("Успех", "Настройки применены!")
                # Не сохраняем профиль автоматически при применении, пользователь делает это сам кнопкой "Сохранить"
                self.read_undervolt()
            else:
                messagebox.showerror("Ошибка", f"Не удалось применить:\n{result.stderr}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка:\n{str(e)}")

    def save_profile(self):
        """Сохраняет текущие поля в профиль."""
        name = self.profile_name_var.get()
        if not name:
            messagebox.showwarning("Внимание", "Введите имя профиля.")
            return

        data = {}
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, 'r') as f:
                    data = json.load(f)
            except:
                data = {}

        # Собираем текущие данные
        profile_data = {k: int(v.get()) if not isinstance(v, tk.BooleanVar) else v.get() for k, v in self.vars.items()}

        data[name] = profile_data

        try:
            with open(PROFILES_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            self.update_profile_list()
            messagebox.showinfo("Успех", f"Профиль '{name}' сохранен.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить профиль:\n{str(e)}")

    def load_profile(self):
        """Загружает профиль в поля."""
        name = self.profile_name_var.get()
        if not name or not os.path.exists(PROFILES_FILE):
            messagebox.showwarning("Внимание", "Файл профилей не найден или имя пустое.")
            return

        try:
            with open(PROFILES_FILE, 'r') as f:
                data = json.load(f)
                if name in data:
                    profile_data = data[name]
                    for k, v in profile_data.items():
                        if k in self.vars:
                            self.vars[k].set(v)
                    messagebox.showinfo("Успех", f"Профиль '{name}' загружен. Нажмите 'Применить настройки'.")
                else:
                    messagebox.showwarning("Внимание", f"Профиль '{name}' не найден в файле.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить профиль:\n{str(e)}")

if __name__ == "__main__":
    if os.geteuid() != 0:
        password = ask_password()
        if password:
            cmd = ['sudo', '-S', sys.executable] + sys.argv
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.communicate(input=password.encode() + b'\n')

            if proc.returncode != 0:
                err_root = tk.Tk()
                err_root.withdraw()
                messagebox.showerror("Ошибка авторизации", "Неверный пароль или отказ в доступе sudo.")
                err_root.destroy()
            sys.exit(proc.returncode)
        else:
            sys.exit(1)

    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use('clam')
    except:
        pass

    app = UndervoltGUI(root)
    root.mainloop()
