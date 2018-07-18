import numpy as np
import tensorflow as tf


def build_train(model,
                num_actions,
                optimizer,
                lstm_unit=256,
                state_shape=[84, 84, 1],
                grad_clip=40.0,
                value_factor=0.5,
                policy_factor=1.0,
                entropy_factor=0.01,
                scope='a3c',
                reuse=None):
    with tf.variable_scope(scope, reuse=reuse):
        # placeholers
        obs_input = tf.placeholder(tf.float32, [None] + state_shape, name='obs')
        rnn_state_ph0 = tf.placeholder(
            tf.float32, [1, lstm_unit], name='rnn_state_0')
        rnn_state_ph1 = tf.placeholder(
            tf.float32, [1, lstm_unit], name='rnn_state_1')
        last_actions_ph = tf.placeholder(tf.int32, [None], name="last_action")
        rewards_ph = tf.placeholder(tf.float32, [None], name="reward")

        # placeholders for A3C update
        actions_ph = tf.placeholder(tf.uint8, [None], name='action')
        target_values_ph = tf.placeholder(tf.float32, [None], name='value')
        advantages_ph = tf.placeholder(tf.float32, [None], name='advantage')

        # rnn state in tuple
        rnn_state_tuple = tf.contrib.rnn.LSTMStateTuple(
            rnn_state_ph0, rnn_state_ph1)

        # network outpus
        last_actions_one_hot = tf.one_hot(
            last_actions_ph, num_actions, dtype=tf.float32)
        policy, value, state_out = model(
            obs_input, last_actions_one_hot, rewards_ph,
            rnn_state_tuple, num_actions, lstm_unit, scope='model')

        actions_one_hot = tf.one_hot(actions_ph, num_actions, dtype=tf.float32)
        log_policy = tf.log(tf.clip_by_value(policy, 1e-20, 1.0))
        log_prob = tf.reduce_sum(log_policy * actions_one_hot, [1])

        # loss
        advantages  = tf.reshape(advantages_ph, [-1, 1])
        target_values = tf.reshape(target_values_ph, [-1, 1])
        with tf.variable_scope('value_loss'):
            value_loss = tf.reduce_sum((target_values - value) ** 2)
        with tf.variable_scope('entropy_penalty'):
            entropy = -tf.reduce_sum(policy * log_policy)
        with tf.variable_scope('policy_loss'):
            policy_loss = tf.reduce_sum(log_prob * advantages)
        loss = value_factor * value_loss\
            - policy_factor * policy_loss - entropy_factor * entropy

        # local network weights
        local_vars = tf.get_collection(
            tf.GraphKeys.TRAINABLE_VARIABLES, scope)
        # global network weights
        global_vars = tf.get_collection(
            tf.GraphKeys.TRAINABLE_VARIABLES, 'global')

        # gradients
        gradients = tf.gradients(loss, local_vars)
        gradients = [tf.clip_by_norm(g, grad_clip) for g in gradients]

        optimize_expr = optimizer.apply_gradients(zip(gradients, global_vars))

        update_local_expr = []
        for local_var, global_var in zip(local_vars, global_vars):
            update_local_expr.append(local_var.assign(global_var))
        update_local_expr = tf.group(*update_local_expr)

        def update_local(sess=None):
            if sess is None:
                sess = tf.get_default_session()
            sess.run(update_local_expr)

        def train(obs, rnn_state0, rnn_state1, actions, rewards,
                  last_actions, target_values, advantages, sess=None):
            if sess is None:
                sess = tf.get_default_session()
            feed_dict = {
                obs_input: obs,
                rnn_state_ph0: rnn_state0,
                rnn_state_ph1: rnn_state1,
                actions_ph: actions,
                last_actions_ph: last_actions,
                rewards_ph: rewards,
                target_values_ph: target_values,
                advantages_ph: advantages
            }
            loss_val, _ = sess.run([loss, optimize_expr], feed_dict=feed_dict)
            return loss_val

        def act(obs, action, reward, rnn_state0, rnn_state1, sess=None):
            if sess is None:
                sess = tf.get_default_session()
            feed_dict = {
                obs_input: obs,
                last_actions_ph: action,
                rewards_ph: reward,
                rnn_state_ph0: rnn_state0,
                rnn_state_ph1: rnn_state1
            }
            return sess.run([policy, value, state_out], feed_dict=feed_dict)

    return act, train, update_local
