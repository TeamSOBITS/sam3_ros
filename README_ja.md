<a name="readme-top"></a>

[EN](README.md) | [JA](README_ja.md)

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]

# SAM3 ROS

<details>
  <summary>目次</summary>
  <ol>
    <li>
      <a href="#概要">概要</a>
    </li>
    <li>
      <a href="#セットアップ">セットアップ</a>
      <ul>
        <li><a href="#環境条件">環境条件</a></li>
        <li><a href="#インストール方法">インストール方法</a></li>
        <li><a href="#SAM3-ウェイトファイルのダウンロード">SAM3 ウェイトファイルのダウンロード</a></li>
      </ul>
    </li>
    <li><a href="#実行操作方法">実行・操作方法</a></li>
    <li><a href="#パラメーター">パラメーター</a></li>
    <li><a href="#トピック">トピック</a></li>
    <li><a href="#デモ">デモ</a></li>
    <li><a href="#参考文献">参考文献</a></li>
  </ol>
</details>

## 概要
`sam3_ros` は，Meta が公開した Segment Anything Model 3（SAM3）を ROS 2 で利用するためのライフサイクル対応ラッパーパッケージです．

**テキストプロンプトに基づくインスタンスセグメンテーション**を行い，結果を標準的な ROS 2 メッセージとして配信します．

**主な機能：**
- テキストプロンプトによる物体セグメンテーション（シングル・マルチクラス対応）
- インスタンスごとのバウンディングボックス出力（`Detection2DArray`）
- インスタンスごとのマスク出力（`DetectMaskArray`）※ピクセル座標・マスク画像の出力も対応
- アノテーション付き可視化画像の出力
- 画像サブスクリプションから切り離されたタイマー駆動の推論ループ
- ROS 2 ライフサイクル完全対応（`configure` → `activate` → `deactivate` → `cleanup`）
- 全パラメーターを `ros2 param set` でランタイムに変更可能

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


## セットアップ

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


### 環境条件

| システム | バージョン |
| -------- | ---------- |
| Ubuntu   | 24.04 (Noble Numbat) |
| ROS 2    | Jazzy Jalisco |
| Python   | 3.12 |

### インストール方法
1. ROS 2 の `src` フォルダに移動します．
   ```sh
   cd ~/colcon_ws/src/
   ```
2. 本レポジトリをクローンします．
   ```sh
   git clone https://github.com/TeamSOBITS/sam3_ros.git
   ```
3. レポジトリの中へ移動し，依存パッケージをインストールします．
   ```sh
   cd sam3_ros
   bash install.sh
   ```
4. パッケージをビルドします．
   ```sh
   cd ~/colcon_ws/
   colcon build --symlink-install
   source install/setup.bash
   ```

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


### SAM3 ウェイトファイルのダウンロード
SAM3 用の `sam3.pt` と SAM3.1 用の `sam3.1_multiplex.pt` の2種類のチェックポイントを使用できます．

ライセンスの都合上，重みファイルは自動でダウンロードされません．
使用するチェックポイントを**事前に手動でダウンロードしてください**．

1. Hugging Face 上の [**SAM3 モデルページ**](https://huggingface.co/facebook/sam3) または [**SAM3.1 モデルページ**](https://huggingface.co/facebook/sam3.1) にアクセスし，重みファイルへのアクセスをリクエストします．

2. 承認後，[`sam3.pt`](https://huggingface.co/facebook/sam3/resolve/main/sam3.pt?download=true) または [`sam3.1_multiplex.pt`](https://huggingface.co/facebook/sam3.1/resolve/main/sam3.1_multiplex.pt?download=true) をダウンロードします．

3. ダウンロードしたファイルを[weight](./weights)のディレクトリに配置します.

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


## 実行・操作方法

1. カメラを起動し，`image_topic_name` をカメラトピックに合わせて起動します：
   ```sh
   ros2 launch sam3_ros sam3.launch.py image_topic_name:=/camera/color/image_raw
   ```

2. 起動時に自動で configure・activate する場合：
   ```sh
   ros2 launch sam3_ros sam3.launch.py auto_configure_2d:=true auto_activate_2d:=true
   ```

3. ライフサイクルを手動で管理する場合：
   ```sh
   ros2 launch sam3_ros sam3.launch.py
   ros2 lifecycle set /sam3_node configure
   ros2 lifecycle set /sam3_node activate
   ```

4. ランタイムにテキストプロンプトを変更する（再起動不要）：
   ```sh
   ros2 param set /sam3_node prompt_text "['chair', 'table']"
   ```

5. モデルを切り替える場合（deactivate → cleanup → パラメーター変更 → configure → activate）：
   ```sh
   ros2 lifecycle set /sam3_node deactivate
   ros2 lifecycle set /sam3_node cleanup
   ros2 param set /sam3_node weight_file sam3.1_multiplex.pt
   ros2 lifecycle set /sam3_node configure
   ros2 lifecycle set /sam3_node activate
   ```

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


## パラメーター

以下のパラメーターはランチファイルまたは `ros2 param set` で設定できます．

| パラメーター名         | 説明                                                                                          | デフォルト値                      | ランタイム変更 |
| ---------------------- | --------------------------------------------------------------------------------------------- | --------------------------------- | -------------- |
| `weight_file`          | SAM3 の重みファイル名                                                                         | `sam3.pt`                         | cleanup 後のみ |
| `weights_path`         | 重みファイルが格納されているディレクトリ                                                       | `<package>/weights`               | cleanup 後のみ |
| `prompt_text`          | セグメンテーション対象クラスのテキストプロンプト（文字列配列）                                | `['']`                            | 可             |
| `threshold`            | マスク生成の信頼度閾値（0.0, 1.0]                                                             | `0.75`                            | 可             |
| `inference_hz`         | 推論レート（Hz）．タイマー駆動で最新フレームを処理する                                        | `5.0`                             | 可             |
| `half`                 | FP16 推論を有効にするか（CUDA が必要）                                                        | `true`                            | 不可           |
| `image_show`           | Ultralytics 組み込みの可視化ウィンドウを有効にするか                                          | `false`                           | 不可           |
| `publish_mask`         | `object_masks` トピック（`DetectMaskArray`）を配信するか                                      | `false`                           | 可             |
| `publish_mask_pixels`  | 各マスクにピクセル座標リスト（`pixel_x`/`pixel_y`）を含めるか                                | `false`                           | 可             |
| `publish_mask_image`   | 各 `DetectMask` にバイナリマスク画像フィールドを含めるか                                      | `false`                           | 可             |
| `image_reliability`    | 画像サブスクリプションの QoS 信頼性（`best_effort`，`reliable`，`system_default` など）        | `best_effort`                     | inactive 時のみ|
| `device`               | 推論デバイス（`cuda`，`cpu`，`cuda:0` など）                                                  | CUDA 利用可能なら `cuda`，否は `cpu` | 不可           |
| `auto_configure_2d`    | 起動時に SAM3 ライフサイクルノードを Configure するか                                         | `false`                           | —              |
| `auto_activate_2d`     | 起動時に SAM3 ライフサイクルノードを Activate するか                                          | `false`                           | —              |
| `auto_configure_3d`    | 起動時に image_to_position ライフサイクルノードを Configure するか                            | `false`                           | —              |
| `auto_activate_3d`     | 起動時に image_to_position ライフサイクルノードを Activate するか                             | `false`                           | —              |
| `use_bbox_to_3d`       | `bbox_to_3d` の3D検出パイプラインを起動するか                                                 | `false`                           | —              |
| `use_mask_to_3d`       | `mask_to_3d` パイプラインを起動するか（`publish_mask:=true` が必要）                          | `false`                           | —              |

> **注意：** `weight_file` および `weights_path` は，ノードが `unconfigured` 状態（`deactivate` + `cleanup` 後）のときのみ変更できます．

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


## トピック

### 配信（Publications）

| トピック名                   | 型                                    | 説明                                       |
| ---------------------------- | ------------------------------------- | ------------------------------------------ |
| `<node>/object_boxes`        | `vision_msgs/Detection2DArray`        | 検出インスタンスごとのバウンディングボックス |
| `<node>/object_masks`        | `sobits_interfaces/DetectMaskArray`   | インスタンスマスク（`publish_mask:=true` 時） |
| `<node>/detected_image`      | `sensor_msgs/Image`                   | アノテーション付き可視化画像               |

### 購読（Subscriptions）

| トピック名             | 型                      | 説明               |
| ---------------------- | ----------------------- | ------------------ |
| `<image_topic_name>`   | `sensor_msgs/Image`     | 入力カメラ画像     |

> `<node>` のデフォルトは `sam3_node` です．ランチ引数 `node_name` で変更できます．

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


## デモ
| 物体検出 | マルチクラス | インスタンスセグメンテーション |
|:---:|:---:|:---:|
| ![](docs/sam3_object_raw.png) | ![](docs/sam3_multiclass_raw.png) | ![](docs/sam3_instant_raw.png) |
| ![](docs/sam3_object_result.png) | ![](docs/sam3_multiclass_result.png) | ![](docs/sam3_instant_result.png) |

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


## 参考文献
* [SAM 3: Segment Anything with Concepts](https://github.com/facebookresearch/sam3)
* [Ultralytics ドキュメント](https://docs.ultralytics.com/ja/models/sam-3/)

[contributors-shield]: https://img.shields.io/github/contributors/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[contributors-url]: https://github.com/TeamSOBITS/sam3_ros/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[forks-url]: https://github.com/TeamSOBITS/sam3_ros/network/members
[stars-shield]: https://img.shields.io/github/stars/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[stars-url]: https://github.com/TeamSOBITS/sam3_ros/stargazers
[issues-shield]: https://img.shields.io/github/issues/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[issues-url]: https://github.com/TeamSOBITS/sam3_ros/issues
[license-shield]: https://img.shields.io/github/license/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[license-url]: LICENSE
