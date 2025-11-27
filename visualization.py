import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

# 他のモジュールからタイル生成機能をインポート
from knowledge_tile_generator import generate_sample_tile

def plot_medical_space(tiles: list):
    """
    Knowledge Tileのリストを受け取り、その座標を3D空間に可視化します。
    点の色は確実性(certainty)スコアに基づいて決定されます。

    Args:
        tiles (list): Knowledge Tileオブジェクトのリスト。
    
    注意:
        この関数を実行するには matplotlib が必要です。
        pip install matplotlib
    """
    if not tiles:
        print("可視化するタイルがありません。")
        return

    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection='3d')

    # データを抽出
    coords_x = [t['coordinates']['medical_space'][0] for t in tiles]
    coords_y = [t['coordinates']['medical_space'][1] for t in tiles]
    coords_z = [t['coordinates']['medical_space'][2] for t in tiles]
    certainty = [t['coordinates']['meta_space'][0] for t in tiles]
    labels = [t['metadata']['topic'] for t in tiles]

    # 散布図をプロット
    # c: 色, cmap: カラーマップ, s: サイズ, alpha: 透明度
    scatter = ax.scatter(coords_x, coords_y, coords_z, 
                         c=certainty, cmap='RdYlGn', s=100, alpha=0.7, vmin=0, vmax=100)

    # 軸ラベルとタイトル
    ax.set_xlabel('臓器系 (Organ System, X)')
    ax.set_ylabel('病態深さ (Pathophysiology Depth, Y)')
    ax.set_zlabel('臨床時間軸 (Clinical Timeline, Z)')
    ax.set_title('Medical Knowledge Space Visualization')

    # カラーバーを追加
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.6)
    cbar.set_label('確実性 (Certainty)')

    # 各点にラベルを付ける (数が多すぎない場合)
    if len(tiles) <= 20:
        for i, label in enumerate(labels):
            ax.text(coords_x[i], coords_y[i], coords_z[i], f' {label}', size=8)
            
    plt.show()

def generate_random_tiles(num_tiles=20):
    """可視化テスト用にランダムなタイルを生成します。"""
    random_tiles = []
    for i in range(num_tiles):
        tile = generate_sample_tile()
        # 座標をランダム化
        tile['metadata']['topic'] = f"Topic {i}"
        tile['coordinates']['medical_space'] = (
            np.random.uniform(10, 100),
            np.random.uniform(10, 100),
            np.random.uniform(10, 100)
        )
        tile['coordinates']['meta_space'] = (
            np.random.uniform(20, 100), # certainty
            np.random.uniform(50, 300), # granularity
            np.random.uniform(50, 100)  # verification
        )
        random_tiles.append(tile)
    return random_tiles

if __name__ == '__main__':
    print("--- 知識空間可視化ツールのデモ ---")
    print("matplotlib が必要です。 `pip install matplotlib`")
    
    # 1. 単一のサンプルタイルを生成して表示
    # print("\n1. 単一のサンプルタイルを可視化します...")
    # single_tile = [generate_sample_tile()]
    # plot_medical_space(single_tile)
    
    # 2. 複数のランダムなタイルを生成して表示
    print("\n2. 複数のランダムなタイルを生成して可視化します...")
    random_sample_tiles = generate_random_tiles(15)
    plot_medical_space(random_sample_tiles)
