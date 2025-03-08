import matplotlib.pyplot as plt
import numpy as np

# Data setup
categories = ['Accuracy', 'Cost (Lower is Better)', 'Efficiency']
traditional_stt = [0.7, 0.5, 1.0]  # STT: lower accuracy, moderate cost, highest efficiency
our_model = [1.0, 0.05, 0.8]       # Our Model: human-level accuracy, very low cost, moderate efficiency
human = [1.0, 1.0, 0.6]            # Human: highest accuracy, highest cost, lowest efficiency

# Positioning
x = np.arange(len(categories))  # Label locations
width = 0.25  # Width of the bars

# Create figure and axis
fig, ax = plt.subplots(figsize=(10, 6))

# Plot bars
bars1 = ax.bar(x - width, traditional_stt, width, label='Traditional STT', color='#FF9999')
bars2 = ax.bar(x, our_model, width, label='Our Model', color='#66B2FF')
bars3 = ax.bar(x + width, human, width, label='Human', color='#99FF99')

# Customize chart
ax.set_ylabel('Normalized Score')
ax.set_title('Comparison of Traditional STT, Our Model, and Human\n(Accuracy, Cost, Efficiency)')
ax.set_xticks(x)
ax.set_xticklabels(categories)
ax.legend()

# Add value labels on top of bars
def autolabel(bars):
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.2f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

autolabel(bars1)
autolabel(bars2)
autolabel(bars3)

# Add annotations for key insights
plt.text(0, 0.75, 'STT fails to clarify\nambiguities (e.g., "1,000 pounds")', ha='center', color='red', fontsize=9)
plt.text(1, 0.3, '20x cheaper\nthan Human', ha='center', color='blue', fontsize=9)
plt.text(2, 1.1, 'STT more efficient\nthan Our Model', ha='center', color='purple', fontsize=9)

# Adjust layout
plt.ylim(0, 1.2)  # Extend y-axis for annotations
plt.tight_layout()

# Show plot
plt.show()