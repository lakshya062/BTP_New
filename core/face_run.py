# core/face_run.py

import cv2
import face_recognition
import os
import numpy as np
import h5py


def load_trained_model_hdf5(model_path="trained_model.hdf5"):
    """Load known face encodings and names from an HDF5 file."""
    known_face_encodings = []
    known_face_names = []
    try:
        with h5py.File(model_path, 'r') as f:
            for person_name in f.keys():
                encodings = f[f"{person_name}/encodings"][:]
                names = f[f"{person_name}/names"][:]
                known_face_encodings.extend(encodings)
                known_face_names.extend([name.decode('utf-8') for name in names])
    except Exception as e:
        print(f"Error loading trained model from {model_path}: {e}")
    return known_face_encodings, known_face_names


def process_frame(args):
    """Process a single video frame for face recognition."""
    frame, known_face_encodings, known_face_names = args
    try:
        # Resize frame for faster processing
        frame_small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        face_locations = face_recognition.face_locations(frame_small)
        face_encodings = face_recognition.face_encodings(frame_small, face_locations)
        face_names = []
        for face_encoding in face_encodings:
            # Compare face encodings with known encodings
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
            name = "Unknown"
            if True in matches:
                first_match_index = matches.index(True)
                name = known_face_names[first_match_index]
            face_names.append(name)
        return frame, face_locations, face_names
    except Exception as e:
        print(f"Error processing frame for face recognition: {e}")
        return frame, [], []


def append_user_to_model_hdf5(user_name, face_encodings, model_path="trained_model.hdf5"):
    """Append a new user's encodings to the HDF5 model."""
    if not face_encodings:
        return False
    # Load existing file or create if not exist
    mode = 'a' if os.path.exists(model_path) else 'w'
    with h5py.File(model_path, mode) as f:
        if user_name in f.keys():
            # Already exists user, just append
            existing_enc = f[f"{user_name}/encodings"]
            existing_names = f[f"{user_name}/names"]
            all_enc = np.concatenate((existing_enc[:], np.array(face_encodings)), axis=0)
            all_names = np.concatenate((existing_names[:], np.array([user_name] * len(face_encodings), dtype='S')), axis=0)

            # Delete old datasets
            del f[f"{user_name}/encodings"]
            del f[f"{user_name}/names"]

            # Create new datasets
            f.create_dataset(f"{user_name}/encodings", data=all_enc, compression="gzip")
            f.create_dataset(f"{user_name}/names", data=all_names, compression="gzip")
        else:
            # Create new user group
            f.create_dataset(f"{user_name}/encodings", data=np.array(face_encodings), compression="gzip")
            f.create_dataset(f"{user_name}/names", data=np.array([user_name] * len(face_encodings), dtype='S'), compression="gzip")
    return True
