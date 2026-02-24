import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QCheckBox, QPushButton, QRadioButton, 
                             QButtonGroup, QSpinBox, QGroupBox)
from PyQt5.QtCore import Qt
from PIL import Image, ImageOps


class ImageProcessorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('多功能图片画幅处理工具')
        self.resize(500, 400)
        self.setAcceptDrops(True)

        main_layout = QVBoxLayout()

        # === 1. 顶部控制区：处理模式和尺寸标准 ===
        top_controls_layout = QHBoxLayout()

        # 1.1 处理模式选择 (扩图 vs 裁切)
        mode_group = QGroupBox("处理模式")
        mode_layout = QHBoxLayout()
        self.radio_expand = QRadioButton("扩图 (填充黑边)")
        self.radio_crop = QRadioButton("裁切 (中心裁切)")
        self.radio_expand.setChecked(True) # 默认扩图
        mode_layout.addWidget(self.radio_expand)
        mode_layout.addWidget(self.radio_crop)
        mode_group.setLayout(mode_layout)
        top_controls_layout.addWidget(mode_group)

        # 1.2 尺寸标准选择 (比例 vs 像素)
        size_type_group = QGroupBox("尺寸标准")
        size_type_layout = QHBoxLayout()
        self.radio_ratio = QRadioButton("画幅比例")
        self.radio_pixels = QRadioButton("指定像素")
        self.radio_ratio.setChecked(True) # 默认比例
        self.radio_ratio.toggled.connect(self.on_size_type_changed)
        size_type_layout.addWidget(self.radio_ratio)
        size_type_layout.addWidget(self.radio_pixels)
        size_type_group.setLayout(size_type_layout)
        top_controls_layout.addWidget(size_type_group)

        main_layout.addLayout(top_controls_layout)

        # === 2. 数值输入区 ===
        input_layout = QHBoxLayout()
        input_layout.addStretch()

        self.spin_w = QSpinBox()
        self.spin_w.setRange(1, 999)
        self.spin_w.setValue(16)
        self.spin_w.setStyleSheet("font-size: 16px; padding: 5px;")
        
        self.divider_label = QLabel(":")
        self.divider_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.spin_h = QSpinBox()
        self.spin_h.setRange(1, 999)
        self.spin_h.setValue(9)
        self.spin_h.setStyleSheet("font-size: 16px; padding: 5px;")

        input_layout.addWidget(self.spin_w)
        input_layout.addWidget(self.divider_label)
        input_layout.addWidget(self.spin_h)
        input_layout.addStretch()
        main_layout.addLayout(input_layout)

        # === 3. 拖拽区域 ===
        self.drop_label = QLabel("将图片拖拽到这里\n\n(将根据上方设置自动处理)", self)
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 3px dashed #aaa;
                border-radius: 10px;
                background-color: #f9f9f9;
                font-size: 16px;
                color: #555;
                margin-top: 10px;
                margin-bottom: 10px;
            }
        """)
        main_layout.addWidget(self.drop_label, stretch=1)

        # === 4. 底部选项与钉固 ===
        options_layout = QHBoxLayout()
        self.replace_checkbox = QCheckBox("替换原图片 (请谨慎勾选)", self)
        self.replace_checkbox.setStyleSheet("font-size: 13px;")
        options_layout.addWidget(self.replace_checkbox)
        options_layout.addStretch()

        self.pin_button = QPushButton("📌 钉固窗口", self)
        self.pin_button.setCheckable(True)
        self.pin_button.setStyleSheet("font-size: 13px; padding: 5px 10px;")
        self.pin_button.clicked.connect(self.toggle_pin)
        options_layout.addWidget(self.pin_button)

        main_layout.addLayout(options_layout)

        # === 5. 状态栏 ===
        self.status_label = QLabel("就绪。调整上方参数后，将图片拖入虚线框内...", self)
        self.status_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 5px;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    # --- 信号槽交互逻辑 ---
    def on_size_type_changed(self):
        """当切换 比例/像素 选项时，动态更新输入框的范围和默认值"""
        if self.radio_ratio.isChecked():
            self.spin_w.setRange(1, 999)
            self.spin_h.setRange(1, 999)
            self.spin_w.setValue(16)
            self.spin_h.setValue(9)
            self.divider_label.setText(" : ")
        else:
            self.spin_w.setRange(1, 99999)
            self.spin_h.setRange(1, 99999)
            self.spin_w.setValue(1920)
            self.spin_h.setValue(1080)
            self.divider_label.setText(" x ")

    def toggle_pin(self):
        """切换窗口置顶状态"""
        flags = self.windowFlags()
        if self.pin_button.isChecked():
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
            self.pin_button.setText("📍 取消钉固")
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
            self.pin_button.setText("📌 钉固窗口")
        self.show()

    # --- 拖放事件 ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.process_files(files)

    # --- 核心图像处理 ---
    def process_files(self, files):
        is_replace = self.replace_checkbox.isChecked()
        mode = "expand" if self.radio_expand.isChecked() else "crop"
        size_type = "ratio" if self.radio_ratio.isChecked() else "pixels"
        val_w = self.spin_w.value()
        val_h = self.spin_h.value()
        
        success_count = 0
        valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')

        for file_path in files:
            if file_path.lower().endswith(valid_extensions):
                try:
                    self.status_label.setText(f"正在处理: {os.path.basename(file_path)}...")
                    QApplication.processEvents()

                    self.process_single_image(file_path, mode, size_type, val_w, val_h, is_replace)
                    success_count += 1
                except Exception as e:
                    print(f"处理 {file_path} 时出错: {e}")

        self.status_label.setText(f"处理完成！成功处理了 {success_count} 张图片。")

    def process_single_image(self, input_path, mode, size_type, val_w, val_h, is_replace):
        with Image.open(input_path) as img_temp:
            img = img_temp.copy()

        # 统一处理透明通道，转为黑底 RGB，避免裁切/扩图后出现透明或失真
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (0, 0, 0))
            if 'A' in img.getbands():
                bg.paste(img, mask=img.getchannel('A'))
            else:
                bg.paste(img)
            img = bg
        else:
            img = img.convert("RGB")

        orig_w, orig_h = img.size
        result_img = None

        if size_type == "ratio":
            # --- 按比例处理 ---
            target_ratio = val_w / val_h
            curr_ratio = orig_w / orig_h

            if mode == "expand":
                # 扩图：计算需要多大的底图才能包住原图
                if curr_ratio > target_ratio:
                    t_w = orig_w
                    t_h = int(orig_w / target_ratio)
                else:
                    t_w = int(orig_h * target_ratio)
                    t_h = orig_h
                # ImageOps.pad 会将原图居中贴在指定大小的黑底上
                result_img = ImageOps.pad(img, (t_w, t_h), color=(0, 0, 0))
                
            elif mode == "crop":
                # 裁切：计算在原图中能框出的最大符合比例的矩形
                if curr_ratio > target_ratio:
                    t_w = int(orig_h * target_ratio)
                    t_h = orig_h
                else:
                    t_w = orig_w
                    t_h = int(orig_w / target_ratio)
                left = (orig_w - t_w) // 2
                top = (orig_h - t_h) // 2
                result_img = img.crop((left, top, left + t_w, top + t_h))

        else:
            # --- 按指定像素处理 ---
            t_w, t_h = val_w, val_h
            if mode == "expand":
                # 扩图：自动缩放原图以放入指定像素内，并填充黑边
                result_img = ImageOps.pad(img, (t_w, t_h), color=(0, 0, 0))
            elif mode == "crop":
                # 裁切：自动缩放原图以铺满指定像素，多余部分从中心裁掉
                result_img = ImageOps.fit(img, (t_w, t_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

        # 保存结果
        output_path = self.get_output_path(input_path, mode, size_type, val_w, val_h, is_replace)
        result_img.save(output_path, quality=95)

    def get_output_path(self, input_path, mode, size_type, val_w, val_h, is_replace):
        if is_replace:
            return input_path
        
        dir_name, file_name = os.path.split(input_path)
        base_name, ext = os.path.splitext(file_name)
        
        # 根据当前模式生成具有辨识度的后缀名
        mode_str = "扩图" if mode == "expand" else "裁切"
        type_str = f"比例{val_w}比{val_h}" if size_type == "ratio" else f"像素{val_w}x{val_h}"
        
        return os.path.join(dir_name, f"{base_name}_{mode_str}_{type_str}{ext}")


if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    window = ImageProcessorApp()
    window.show()
    sys.exit(app.exec_())
