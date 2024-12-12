# config.py
import mediapipe as mp

mp_pose = mp.solutions.pose

exercise_config = {
    'bicep_curl': {
        'angles': {
            'left_arm': [mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.LEFT_ELBOW, mp_pose.PoseLandmark.LEFT_WRIST],
            'right_arm': [mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_ELBOW, mp_pose.PoseLandmark.RIGHT_WRIST],
        },
        'down_range': (150, 170),
        'up_range': (35, 55),
        'bend_detection': True
    },
    'seated_shoulder_press': {
        'angles': {
            'left_arm': [mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.LEFT_ELBOW, mp_pose.PoseLandmark.LEFT_WRIST],
            'right_arm': [mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_ELBOW, mp_pose.PoseLandmark.RIGHT_WRIST]
        },
        'down_range': (80, 100),
        'up_range': (160, 180),
        'bend_detection': True
    },
    'lateral_raises': {
        'angles': {
            'left_arm': [mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.LEFT_ELBOW, mp_pose.PoseLandmark.LEFT_WRIST],
            'right_arm': [mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_ELBOW, mp_pose.PoseLandmark.RIGHT_WRIST]
        },
        'down_range': (70, 90),
        'up_range': (130, 150),
        'bend_detection': False
    }
}
