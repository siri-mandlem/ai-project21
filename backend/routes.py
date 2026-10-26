from flask import Blueprint, jsonify, request
from backend.models import db, User, Goal, Subject, Session, Progress, Dashboards
from backend.utils import token_required

goals_bp = Blueprint('goals', __name__)
dashboards_bp = Blueprint('dashboards', __name__)

@goals_bp.route('/goals', methods=['POST'])
@token_required
def create_goal(current_user):
    data = request.get_json()
    new_goal = Goal(user_id=current_user.id, **data)
    db.session.add(new_goal)
    db.session.commit()
    return jsonify({'message': 'Goal created successfully'}), 201

@goals_bp.route('/goals', methods=['GET'])
@token_required
def get_goals(current_user):
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    return jsonify([goal.to_dict() for goal in goals]), 200

@goals_bp.route('/goals/<int:goal_id>', methods=['PUT'])
@token_required
def update_goal(current_user, goal_id):
    goal = Goal.query.get(goal_id)
    if goal.user_id != current_user.id:
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    goal.progress = data.get('progress')
    db.session.commit()
    return jsonify({'message': 'Goal updated successfully'}), 200

@goals_bp.route('/goals/<int:goal_id>', methods=['DELETE'])
@token_required
def delete_goal(current_user, goal_id):
    goal = Goal.query.get(goal_id)
    if goal.user_id != current_user.id:
        return jsonify({'message': 'Not authorized'}), 403
    db.session.delete(goal)
    db.session.commit()
    return jsonify({'message': 'Goal deleted successfully'}), 200

@dashboards_bp.route('/dashboards', methods=['GET'])
@token_required
def get_dashboards(current_user):
    dashboards = Dashboards.query.filter_by(user_id=current_user.id).all()
    return jsonify([dashboard.to_dict() for dashboard in dashboards]), 200

# Add more routes for other models as needed
