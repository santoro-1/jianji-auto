# Pixel Apple Cat look mechanics

The red pixel apple shell is the stable body and must remain upright, centered, and planted on the same tiny feet in every direction. The black stem, chunky dark outline, apple silhouette, hands, and feet stay fixed in scale and construction; the whole apple never rotates, skews, or rocks to fake gaze.

The photographic cat face is the natural aiming surface. The eyes lead, followed by a small coherent turn or pitch of the muzzle and face plane; the ears and cheek visibility follow subtly inside the apple opening. Preserve the same cat identity, fur colors, eye construction, nose, muzzle, and photographic texture. Do not replace the eyes with pixel dots, googly eyes, or painted pupils.

Cardinal pose families:

- `000 up`: eyes aim toward the top edge; muzzle pitches slightly upward; lower eyelids open subtly; ears remain visible and symmetric enough to read as the same cat.
- `090 screen-right`: pupils, nose tip, and muzzle shift clearly to the viewer's right of head center; more of the cat's screen-left cheek is visible and the screen-right cheek is slightly occluded.
- `180 down`: eyes aim toward the bottom edge; muzzle pitches slightly down; upper eyelids lower subtly while the face remains clearly visible.
- `270 screen-left`: pupils, nose tip, and muzzle shift clearly to the viewer's left of head center; more of the cat's screen-right cheek is visible and the screen-left cheek is slightly occluded.

Diagonals interpolate evenly between the adjacent cardinal face families in 22.5-degree steps. Keep the apple body, stem, outline, hands, feet, baseline, and overall silhouette unchanged; only the cat face plane, eyes, eyelids, muzzle, ears, and tiny internal cheek occlusion may move. Maintain a smooth clockwise loop with no facial identity jump at `157.5 -> 180` or `337.5 -> 000`.

Motion budget: each adjacent step moves the eyes and muzzle by a small, roughly equal amount. Head/face translation stays inside the apple opening, ear visibility changes gradually, and no direction introduces a larger scale change or pose jump than its neighbors.
