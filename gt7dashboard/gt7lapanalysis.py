import numpy as np
from typing import Dict, List, Tuple
from gt7dashboard.gt7lap import Lap
import logging

logger = logging.getLogger(__name__)

class LapAnalyzer:
    """Analyzes and compares lap telemetry data to identify performance improvements"""
    
    def __init__(self):
        # Configure analysis parameters
        self.track_segment_length = 25  # meters for track segmentation
        self.significant_speed_diff = 5  # km/h speed difference threshold
        self.significant_line_diff = 2.0  # meters of racing line deviation threshold
    
    def analyze_laps(self, reference_lap: Lap, comparison_lap: Lap) -> Dict:
        """Compare laps and generate improvement analysis"""
        if not reference_lap or not comparison_lap:
            return {"error": "Both reference lap and comparison lap are required"}
        
        # Segment the track and analyze each segment
        track_segments = self._segment_track(reference_lap)
        
        # Track overall time differences
        overall_analysis = {
            "total_time_diff": comparison_lap.lap_finish_time - reference_lap.lap_finish_time,
            "segments": [],
            "key_improvements": []
        }
        
        # Analyze each track segment
        for segment_idx, segment in enumerate(track_segments):
            segment_analysis = self._analyze_segment(
                segment_idx,
                segment, 
                reference_lap, 
                comparison_lap
            )
            
            if segment_analysis:
                overall_analysis["segments"].append(segment_analysis)
                
                # Add significant findings to key improvements
                if "improvement_potential" in segment_analysis and segment_analysis["improvement_potential"] > 0.1:
                    overall_analysis["key_improvements"].append({
                        "segment": segment_idx,
                        "suggestion": segment_analysis["suggestion"],
                        "potential_gain": segment_analysis["improvement_potential"]
                    })
        
        # Sort improvements by potential time gain
        overall_analysis["key_improvements"] = sorted(
            overall_analysis["key_improvements"], 
            key=lambda x: x["potential_gain"], 
            reverse=True
        )
        
        return overall_analysis
    
    def _segment_track(self, lap: Lap) -> List[Dict]:
        """Divide track into logical segments for analysis"""
        segments = []
        
        # Use position data to segment the track
        total_points = len(lap.data_position_x)
        if total_points == 0:
            return segments
            
        current_segment = {
            "start_idx": 0,
            "points": []
        }
        
        # Simple distance-based segmentation
        last_x, last_z = lap.data_position_x[0], lap.data_position_z[0]
        distance_accumulator = 0
        
        for i in range(total_points):
            x, z = lap.data_position_x[i], lap.data_position_z[i]
            
            # Calculate distance from last point
            segment_distance = np.sqrt((x - last_x)**2 + (z - last_z)**2)
            distance_accumulator += segment_distance
            
            # Add point to current segment
            current_segment["points"].append(i)
            
            # If we've accumulated enough distance, close this segment
            if distance_accumulator >= self.track_segment_length:
                current_segment["end_idx"] = i
                current_segment["type"] = self._determine_segment_type(lap, current_segment)
                segments.append(current_segment)
                
                # Start new segment
                current_segment = {
                    "start_idx": i,
                    "points": []
                }
                distance_accumulator = 0
            
            last_x, last_z = x, z
        
        # Add final segment if not empty
        if current_segment["points"]:
            current_segment["end_idx"] = total_points - 1
            current_segment["type"] = self._determine_segment_type(lap, current_segment)
            segments.append(current_segment)
            
        return segments
    
    def _determine_segment_type(self, lap: Lap, segment: Dict) -> str:
        """Determine if segment is a straight, corner, braking zone, etc."""
        start_idx = segment["start_idx"]
        end_idx = segment["end_idx"]
        points = segment["points"]
        
        # Check braking patterns
        braking_sum = sum(lap.data_braking[i] for i in points if i < len(lap.data_braking))
        avg_braking = braking_sum / len(points) if points else 0
        
        # Check throttle patterns
        throttle_sum = sum(lap.data_throttle[i] for i in points if i < len(lap.data_throttle))
        avg_throttle = throttle_sum / len(points) if points else 0
        
        # Calculate curvature using position data
        if len(points) >= 3:
            # Simple curvature estimate
            try:
                x_values = [lap.data_position_x[i] for i in [points[0], points[len(points)//2], points[-1]]]
                z_values = [lap.data_position_z[i] for i in [points[0], points[len(points)//2], points[-1]]]
                
                # Check if points form a substantial curve
                dx1, dz1 = x_values[1]-x_values[0], z_values[1]-z_values[0]
                dx2, dz2 = x_values[2]-x_values[1], z_values[2]-z_values[1]
                
                angle_change = abs(np.arctan2(dz2, dx2) - np.arctan2(dz1, dx1))
                
                if angle_change > 0.2:  # Threshold for corner detection
                    if avg_braking > 0.5:
                        return "braking_zone"
                    return "corner"
            except:
                pass
        
        # Default to straight if nothing else matches
        if avg_throttle > 0.8:
            return "straight"
        elif avg_braking > 0.5:
            return "braking_zone"
        else:
            return "corner"
    
    def _analyze_segment(self, segment_idx: int, segment: Dict, ref_lap: Lap, comp_lap: Lap) -> Dict:
        """Analyze a specific track segment and identify improvements"""
        start_idx = segment["start_idx"]
        end_idx = segment["end_idx"]
        segment_type = segment["type"]
        
        # Skip analysis if insufficient data points
        if start_idx >= len(comp_lap.data_time) or end_idx >= len(ref_lap.data_time):
            return None
        
        # Calculate time difference in this segment
        ref_segment_time = ref_lap.data_time[end_idx] - ref_lap.data_time[start_idx]
        comp_segment_time = comp_lap.data_time[min(end_idx, len(comp_lap.data_time)-1)] - comp_lap.data_time[min(start_idx, len(comp_lap.data_time)-1)]
        time_diff = comp_segment_time - ref_segment_time
        
        analysis = {
            "segment_idx": segment_idx,
            "segment_type": segment_type,
            "time_diff": time_diff,
            "start_distance": ref_lap.data_time[start_idx],
            "end_distance": ref_lap.data_time[end_idx],
        }
        
        # Only do detailed analysis if there's a significant time difference
        if abs(time_diff) < 0.05:  # Less than 50ms difference
            return analysis
            
        # Get indices for comparable points
        ref_indices = segment["points"]
        comp_indices = self._map_indices_between_laps(ref_indices, ref_lap, comp_lap)
        
        # Calculate speed differences
        ref_speeds = [ref_lap.data_speed[i] for i in ref_indices if i < len(ref_lap.data_speed)]
        comp_speeds = [comp_lap.data_speed[i] for i in comp_indices if i < len(comp_lap.data_speed)]
        
        # Make sure we have data to compare
        if not ref_speeds or not comp_speeds:
            return analysis
            
        # Calculate average and max speeds
        avg_ref_speed = sum(ref_speeds) / len(ref_speeds)
        avg_comp_speed = sum(comp_speeds) / len(comp_speeds)
        max_ref_speed = max(ref_speeds)
        max_comp_speed = max(comp_speeds)
        
        speed_diff = avg_comp_speed - avg_ref_speed
        analysis["speed_diff"] = speed_diff
        
        # Racing line analysis
        line_deviation = self._calculate_line_deviation(ref_indices, comp_indices, ref_lap, comp_lap)
        analysis["line_deviation"] = line_deviation
        
        # Check throttle application
        ref_throttle = [ref_lap.data_throttle[i] for i in ref_indices if i < len(ref_lap.data_throttle)]
        comp_throttle = [comp_lap.data_throttle[i] for i in comp_indices if i < len(comp_lap.data_throttle)]
        
        if ref_throttle and comp_throttle:
            analysis["throttle_diff"] = sum(comp_throttle) / len(comp_throttle) - sum(ref_throttle) / len(ref_throttle)
        
        # Check braking application
        ref_brake = [ref_lap.data_braking[i] for i in ref_indices if i < len(ref_lap.data_braking)]
        comp_brake = [comp_lap.data_braking[i] for i in comp_indices if i < len(comp_lap.data_braking)]
        
        if ref_brake and comp_brake:
            analysis["brake_diff"] = sum(comp_brake) / len(comp_brake) - sum(ref_brake) / len(ref_brake)
        
        # Generate improvement suggestion based on segment type and analysis
        suggestion, improvement_potential = self._generate_suggestion(segment_type, analysis)
        analysis["suggestion"] = suggestion
        analysis["improvement_potential"] = improvement_potential
        
        return analysis
    
    def _map_indices_between_laps(self, ref_indices: List[int], ref_lap: Lap, comp_lap: Lap) -> List[int]:
        """Map indices from reference lap to comparison lap based on track position"""
        comp_indices = []
        
        for ref_idx in ref_indices:
            if ref_idx >= len(ref_lap.data_position_x):
                continue
                
            # Get reference position
            ref_x = ref_lap.data_position_x[ref_idx]
            ref_z = ref_lap.data_position_z[ref_idx]
            
            # Find closest point in comparison lap
            best_dist = float('inf')
            best_idx = 0
            
            for i in range(len(comp_lap.data_position_x)):
                comp_x = comp_lap.data_position_x[i]
                comp_z = comp_lap.data_position_z[i]
                
                dist = (ref_x - comp_x)**2 + (ref_z - comp_z)**2
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
            
            comp_indices.append(best_idx)
        
        return comp_indices
    
    def _calculate_line_deviation(self, ref_indices: List[int], comp_indices: List[int], 
                                ref_lap: Lap, comp_lap: Lap) -> float:
        """Calculate average deviation between racing lines"""
        total_deviation = 0.0
        count = 0
        
        for i in range(min(len(ref_indices), len(comp_indices))):
            ref_idx = ref_indices[i]
            comp_idx = comp_indices[i]
            
            if ref_idx >= len(ref_lap.data_position_x) or comp_idx >= len(comp_lap.data_position_x):
                continue
                
            ref_x = ref_lap.data_position_x[ref_idx]
            ref_z = ref_lap.data_position_z[ref_idx]
            comp_x = comp_lap.data_position_x[comp_idx]
            comp_z = comp_lap.data_position_z[comp_idx]
            
            deviation = np.sqrt((ref_x - comp_x)**2 + (ref_z - comp_z)**2)
            total_deviation += deviation
            count += 1
        
        return total_deviation / count if count > 0 else 0.0
    
    def _generate_suggestion(self, segment_type: str, analysis: Dict) -> Tuple[str, float]:
        """Generate improvement suggestion based on segment analysis"""
        time_diff = analysis.get("time_diff", 0)
        
        # No improvement needed
        if time_diff <= 0:
            return "Good job on this section!", 0.0
        
        suggestion = ""
        potential_gain = min(time_diff, 0.5)  # Cap potential gain estimate at 0.5s per segment
        
        if segment_type == "corner":
            line_deviation = analysis.get("line_deviation", 0)
            speed_diff = analysis.get("speed_diff", 0)
            
            if line_deviation > self.significant_line_diff:
                suggestion = "Take a tighter racing line through this corner"
            elif speed_diff < -self.significant_speed_diff:
                throttle_diff = analysis.get("throttle_diff", 0)
                if throttle_diff < -0.1:
                    suggestion = "Apply more throttle through this corner"
                else:
                    suggestion = "Carry more speed through this corner"
            else:
                suggestion = "Work on corner technique - brake less, turn in earlier"
                
        elif segment_type == "braking_zone":
            brake_diff = analysis.get("brake_diff", 0)
            
            if brake_diff > 0.1:
                suggestion = "Brake later and less aggressively"
            else:
                suggestion = "Improve braking technique - more trail braking"
                
        elif segment_type == "straight":
            speed_diff = analysis.get("speed_diff", 0)
            
            if speed_diff < -5:
                suggestion = "Apply full throttle earlier exiting the previous corner"
            else:
                suggestion = "Focus on exit speed from previous corner"
                
        else:
            suggestion = "Lost time in this section - review replay"
        
        return suggestion, potential_gain